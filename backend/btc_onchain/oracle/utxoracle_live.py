
# btc_onchain/oracle/utxoracle_live.py
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Iterable, List, Tuple

# ---- Configuration (you can move these to settings if you prefer) ----
# log10 bins from 1e-6 to 1e6 BTC, 200 bins per decade
LOG_MIN = -6
LOG_MAX =  6
BINS_PER_DECADE = 200
ROUND_BTC_BIN_IDX = [
    201,401,461,496,540,601,661,696,740,801,861,896,940,1001,1061,1096,1140,1201
]  # copied from UTXOracle
ROUND_BTC_SMOOTH_FACTOR = 0.5
SMOOTH_WEIGHT = 0.65
SPIKE_WEIGHT = 1.0

# Slide limits (in “bin offsets”) roughly corresponding to price range.
# You can calibrate these with your price_min/max grid if you like.
MIN_SLIDE = -141  # ~ $500k in original mapping
MAX_SLIDE =  201  # ~ $5k in original mapping

# Center mapping in original: if slide==0, 0.001 BTC ~= $100 (price $100k)
CENTER_P001 = 601
NUM_ELEMENTS = 803
MEAN = 411
STD_DEV = 201

# Spike stencil weights (same as upstream)
def _spike_stencil() -> List[float]:
    s = [0.0]*NUM_ELEMENTS
    s[40] = 0.001300198324984352
    s[141]= 0.001676746949820743
    s[201]= 0.003468805546942046
    s[202]= 0.001991977522512513
    s[236]= 0.001905066647961839
    s[261]= 0.003341772718156079
    s[262]= 0.002588902624584287
    s[296]= 0.002577893841190244
    s[297]= 0.002733728814200412
    s[340]= 0.003076117748975647
    s[341]= 0.005613067550103145
    s[342]= 0.003088253178535568
    s[400]= 0.002918457489366139
    s[401]= 0.006174500465286022
    s[402]= 0.004417068070043504
    s[403]= 0.002628663628020371
    s[436]= 0.002858828161543839
    s[461]= 0.004097463611984264
    s[462]= 0.003345917406120509
    s[496]= 0.002521467726855856
    s[497]= 0.002784125730361008
    s[541]= 0.003792850444811335
    s[601]= 0.003688240815848247
    s[602]= 0.002392400117402263
    s[636]= 0.001280993059008106
    s[661]= 0.001654665137536031
    s[662]= 0.001395501347054946
    s[741]= 0.001154279140906312
    s[801]= 0.000832244504868709
    return s

def _smooth_stencil() -> List[float]:
    out = []
    for x in range(NUM_ELEMENTS):
        exp_part = -((x - MEAN) ** 2) / (2 * (STD_DEV ** 2))
        out.append( (0.00150 * math.e ** exp_part) + (0.0000005 * x) )
    return out

SPIKES = _spike_stencil()
SMOOTH = _smooth_stencil()

@dataclass
class LiveOracleResult:
    price: float
    confidence: float
    curvature: float
    samples_used: int
    curve_points: List[Tuple[float, float]]  # (price_usd, score) for plotting

# ---- Helpers ----
def _init_log_bins() -> Tuple[List[float], List[float]]:
    bins = [0.0]
    for exp in range(LOG_MIN, LOG_MAX):
        for b in range(BINS_PER_DECADE):
            val = 10 ** (exp + b / BINS_PER_DECADE)
            bins.append(val)
    counts = [0.0] * len(bins)
    return bins, counts

def _insert_amount(bins: List[float], counts: List[float], amount_btc: float, weight: float=1.0) -> None:
    if amount_btc <= 0.0: return
    # find bin index by walking forward (bins are increasing)
    # Simple bound search; could bisect, but this is fine for prototype.
    lo, hi = 0, len(bins)-1
    while lo < hi:
        mid = (lo + hi + 1)//2
        if bins[mid] <= amount_btc:
            lo = mid
        else:
            hi = mid - 1
    idx = max(0, min(lo, len(counts)-1))
    counts[idx] += weight

def _suppress_round_btc(counts: List[float]) -> None:
    for r in ROUND_BTC_BIN_IDX:
        if 1 <= r < len(counts)-1:
            counts[r] = ROUND_BTC_SMOOTH_FACTOR * (counts[r-1] + counts[r+1])

def _normalize_and_clip(counts: List[float], lo_idx: int=201, hi_idx: int=1601, clip: float=0.008) -> None:
    s = sum(counts[lo_idx:hi_idx])
    if s <= 0: return
    for i in range(lo_idx, hi_idx):
        v = counts[i] / s
        counts[i] = v if v <= clip else clip

def _slide_score(curve: List[float], left_idx: int, right_idx: int) -> Tuple[List[float], List[float], List[float]]:
    # returns per-slide scores: total, spikes-only, smooth-only
    totals, spikes, smooths = [], [], []
    for slide in range(MIN_SLIDE, MAX_SLIDE):
        seg = curve[left_idx+slide : right_idx+slide]
        if len(seg) != NUM_ELEMENTS:
            totals.append(0.0); spikes.append(0.0); smooths.append(0.0)
            continue
        sc_spike = sum(a*b for a,b in zip(seg, SPIKES))
        sc_smooth = sum(a*b for a,b in zip(seg, SMOOTH))
        # prefer combined score, with smooth discounted on “wrong regions” as per original
        combined = sc_spike*SPIKE_WEIGHT + sc_smooth*SMOOTH_WEIGHT if slide < 150 else sc_spike*SPIKE_WEIGHT
        totals.append(combined); spikes.append(sc_spike); smooths.append(sc_smooth)
    return totals, spikes, smooths

def _score_confidence(totals: List[float], peak_idx: int) -> Tuple[float, float]:
    # Confidence from peak dominance & curvature proxy
    if not totals: return 0.0, 0.0
    peak = totals[peak_idx]
    med = sorted(totals)[len(totals)//2]
    # second-best score:
    nb = totals.copy()
    nb[peak_idx] = float('-inf')
    second = max(nb)
    # curvature proxy:  peak - average(neighbors)
    left = totals[peak_idx-1] if peak_idx-1 >= 0 else peak
    right = totals[peak_idx+1] if peak_idx+1 < len(totals) else peak
    curvature = max(0.0, peak - 0.5*(left+right))

    # squash into 0..1
    dom1 = peak / (med + 1e-12)
    dom2 = peak / (second + 1e-12)
    conf = math.tanh(0.25*dom1) * math.tanh(0.5*dom2) * math.tanh(0.001*curvature + 1e-9)
    return float(conf), float(curvature)

# ---- Public entry point ----
def estimate_from_outputs(outputs: Iterable[Tuple[float, float]],  # (value_btc, weight)
                          ) -> LiveOracleResult:
    """
    outputs: iterable of (value_btc, weight). weight can be 1.0 if unknown.
    Returns a price/curve/confidence snapshot from current mempool window.
    """
    bins, counts = _init_log_bins()
    # insert values
    used = 0
    for v_btc, w in outputs:
        # filter like UTXOracle: ignore tiny/huge
        if 1e-5 < v_btc < 1e5:
            _insert_amount(bins, counts, v_btc, w if w > 0 else 1.0)
            used += 1

    # preprocess
    _suppress_round_btc(counts)
    _normalize_and_clip(counts)

    # Choose a fixed-length window of exactly NUM_ELEMENTS centered around CENTER_P001
    left = CENTER_P001 - (NUM_ELEMENTS // 2)
    right = left + NUM_ELEMENTS

    totals, spikes, smooths = _slide_score(counts, left, right)
    if not totals or max(totals) <= 0 or used == 0:
        return LiveOracleResult(price=0.0, confidence=0.0, curvature=0.0, samples_used=used, curve_points=[])

    # best slide
    rel_idx = int(max(range(len(totals)), key=totals.__getitem__))   # index into totals
    slide = MIN_SLIDE + rel_idx

    # best price at center point
    idx_center = CENTER_P001 + slide
    usd100_in_btc_best = bins[idx_center]
    p1 = 100.0 / usd100_in_btc_best

    # neighbor blend
    # up
    usd100_in_btc_up = bins[idx_center+1] if idx_center+1 < len(bins) else usd100_in_btc_best
    p_up = 100.0 / usd100_in_btc_up
    sc_up = totals[rel_idx+1] if rel_idx+1 < len(totals) else totals[rel_idx]

    # down
    usd100_in_btc_dn = bins[idx_center-1] if idx_center-1 >= 0 else usd100_in_btc_best
    p_dn = 100.0 / usd100_in_btc_dn
    sc_dn = totals[rel_idx-1] if rel_idx-1 >= 0 else totals[rel_idx]

    # choose the better neighbor and weight by dominance over median
    neighbor_price = p_up if sc_up >= sc_dn else p_dn
    neighbor_score = max(sc_up, sc_dn)
    avg_score = sum(totals)/max(1,len(totals))
    a1 = totals[rel_idx] - avg_score
    a2 = abs(neighbor_score - avg_score)
    if (a1 + a2) <= 0:
        price = p1
    else:
        w1 = a1/(a1+a2); w2 = a2/(a1+a2)
        price = w1*p1 + w2*neighbor_price

    # confidence & curvature
    conf, curv = _score_confidence(totals, rel_idx)

    # assemble a light curve for UI (map slide index → USD price & score)
    pts: List[Tuple[float,float]] = []
    for i, sc in enumerate(totals):
        s = MIN_SLIDE + i
        idx = CENTER_P001 + s
        if 0 <= idx < len(bins):
            pts.append((100.0/bins[idx], sc))

    return LiveOracleResult(price=float(price), confidence=conf, curvature=curv, samples_used=used, curve_points=pts)
