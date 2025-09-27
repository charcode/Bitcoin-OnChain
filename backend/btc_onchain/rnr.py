from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, List
import math
import numpy as np


# ----- helpers -----

def weight_output(n_vout: int, is_rbf: bool) -> float:
    # simple, stable: fewer outputs and non-RBF → a bit more weight
    base = 1.0 / max(1, int(n_vout))
    return base * (0.8 if is_rbf else 1.0)


def nearest_round_distance_usd(x_usd: float, grid: int) -> float:
    if grid <= 0:
        return 0.0
    r = x_usd % grid
    return min(r, grid - r)


# ----- histogram -----

def rnr_histogram_usd(
    outs: Iterable[dict],
    price_usd: float,
    grid: int,
    span_mults: int,
    window_half: float,
) -> List[dict]:
    """
    Build histogram around +/- span_mults multiples of `grid` centered on current price.
    Count outputs whose USD value is within +/- window_half of each multiple.
    """
    if grid <= 0:
        return []

    center = round(price_usd / grid) * grid
    anchors = [center + k * grid for k in range(-span_mults, span_mults + 1)]

    bins = []
    for a in anchors:
        c = 0
        wsum = 0.0
        for o in outs:
            usd = float(o["value_btc"]) * price_usd
            if abs(usd - a) <= window_half:
                c += 1
                wsum += float(o.get("weight", 1.0))
        bins.append({"price": float(a), "count": int(c), "weight_sum": float(wsum)})
    return bins


# ----- RNR search -----

@dataclass
class SearchResult:
    grid_prices: np.ndarray  # candidate prices
    scores: np.ndarray       # baseline-subtracted scores (>=0)
    raw_scores: np.ndarray   # raw before baseline
    best_idx: int
    best_price: float
    best_score: float
    curvature: float

    @property
    def zscores(self) -> np.ndarray:
        # Compatibility alias for old code that expected .zscores
        return self.scores


def _score_for_price(outs: List[dict], price: float, grids: List[int], sigma_usd: float) -> float:
    if not outs:
        return 0.0
    s = 0.0
    inv2sig2 = 1.0 / (2.0 * (sigma_usd ** 2) + 1e-12)
    for o in outs:
        vb = float(o["value_btc"])
        w = float(o.get("weight", 1.0))
        x = vb * price  # USD
        for g in grids:
            if g <= 0:
                continue
            d = nearest_round_distance_usd(x, g)
            # scale per-grid by 1/sqrt(g) to reduce large-grid dominance
            wg = 1.0 / math.sqrt(float(g))
            s += w * wg * math.exp(-(d * d) * inv2sig2)
    return s


def _running_median(y: np.ndarray, k: int) -> np.ndarray:
    # simple median filter; pad at edges
    k = max(3, int(k) | 1)  # force odd
    pad = k // 2
    ypad = np.pad(y, (pad, pad), mode='edge')
    out = np.empty_like(y)
    for i in range(len(y)):
        out[i] = np.median(ypad[i:i + k])
    return out


def rnr_search(
    outs: List[dict],
    price_min: float,
    price_max: float,
    price_step: float,
    sigma_usd: float,
    grids: List[int],
) -> SearchResult:
    if not outs or price_max <= price_min or price_step <= 0:
        P = np.arange(price_min, price_max + 1e-9, max(price_step, 1.0))
        zeros = np.zeros_like(P)
        return SearchResult(P, zeros, zeros, 0, float(price_min), 0.0, 0.0)

    P = np.arange(price_min, price_max + 1e-9, price_step)
    raw = np.empty_like(P)
    for i, p in enumerate(P):
        raw[i] = _score_for_price(outs, float(p), grids, sigma_usd)

    # remove broad baseline so peaks stand out
    med = _running_median(raw, k=max(7, int(15 * (50.0 / price_step))))
    # small EMA to handle slow drift
    ema = np.copy(raw)
    alpha = 0.05
    for i in range(1, len(ema)):
        ema[i] = alpha * raw[i] + (1.0 - alpha) * ema[i - 1]
    baseline = 0.5 * med + 0.5 * ema

    z = raw - baseline
    z = np.maximum(z, 0.0)

    i_best = int(np.argmax(z))
    p_best = float(P[i_best])
    s_best = float(z[i_best])

    # discrete 2nd derivative (scaled by step^2 to be scale-invariant)
    if 0 < i_best < len(z) - 1:
        lap = (z[i_best - 1] - 2.0 * z[i_best] + z[i_best + 1]) / (price_step ** 2)
        curv = -float(lap)  # positive when there is a "sharp" peak
        curv = max(curv, 0.0)
    else:
        curv = 0.0

    return SearchResult(P, z, raw, i_best, p_best, s_best, curv)
