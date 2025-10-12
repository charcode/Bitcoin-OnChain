from __future__ import annotations

import logging
import math
from bisect import bisect_right
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

from ..models import RoundUsdStat
from ..rpc import Rpc
from .fulcrum_client import FulcrumClient

logger = logging.getLogger(__name__)

# Histogram bin configuration (log spaced 200 bins per decade from 1e-6 to 1e5 BTC)
_OUTPUT_BINS: List[float] = [0.0]
for exponent in range(-6, 6):
    for step in range(200):
        _OUTPUT_BINS.append(10 ** (exponent + step / 200))

_BIN_COUNT = len(_OUTPUT_BINS)

# Round BTC bin indices that should be smoothed
_ROUND_BTC_BINS: Sequence[int] = (
    201,
    401,
    461,
    496,
    540,
    601,
    661,
    696,
    740,
    801,
    861,
    896,
    940,
    1001,
    1061,
    1096,
    1140,
    1201,
)

# Smooth stencil configuration
_STENCIL_LENGTH = 803
_STENCIL_MEAN = 411
_STENCIL_STDDEV = 201

_SMOOTH_STENCIL: List[float] = []
for x in range(_STENCIL_LENGTH):
    exp_part = -((x - _STENCIL_MEAN) ** 2) / (2 * (_STENCIL_STDDEV ** 2))
    _SMOOTH_STENCIL.append((0.00150 * math.e ** exp_part) + (0.0000005 * x))

# Spike stencil weights copied from UTXOracle calibration
_SPIKE_WEIGHTS: Dict[int, float] = {
    40: 0.001300198324984352,
    141: 0.001676746949820743,
    201: 0.003468805546942046,
    202: 0.001991977522512513,
    236: 0.001905066647961839,
    261: 0.003341772718156079,
    262: 0.002588902624584287,
    296: 0.002577893841190244,
    297: 0.002733728814200412,
    340: 0.003076117748975647,
    341: 0.005613067550103145,
    342: 0.003088253178535568,
    400: 0.002918457489366139,
    401: 0.006174500465286022,
    402: 0.004417068070043504,
    403: 0.002628663628020371,
    436: 0.002858828161543839,
    461: 0.004097463611984264,
    462: 0.003345917406120509,
    496: 0.002521467726855856,
    497: 0.002784125730361008,
    541: 0.003792850444811335,
    601: 0.003688240815848247,
    602: 0.002392400117402263,
    636: 0.001280993059008106,
    661: 0.001654665137536031,
    662: 0.001395501347054946,
    741: 0.001154279140906312,
    801: 0.000832244504868709,
}

_SPIKE_STENCIL: List[float] = [0.0] * _STENCIL_LENGTH
for idx, weight in _SPIKE_WEIGHTS.items():
    if 0 <= idx < _STENCIL_LENGTH:
        _SPIKE_STENCIL[idx] = weight

# Mapping of USD round amounts to spike indices (grouped when calibration spans multiple bins)
_USD_GROUPS: Dict[int, Sequence[int]] = {
    1: (40,),
    5: (141,),
    10: (201, 202),
    15: (236,),
    20: (261, 262),
    30: (296, 297),
    50: (340, 341, 342),
    100: (400, 401, 402, 403),
    150: (436,),
    200: (461, 462),
    300: (496, 497),
    500: (541,),
    1000: (601, 602),
    1500: (636,),
    2000: (661, 662),
    5000: (741,),
    10000: (801,),
}

_CENTER_P001 = 601
_LEFT_P001 = _CENTER_P001 - int((len(_SPIKE_STENCIL) + 1) / 2)
_RIGHT_P001 = _CENTER_P001 + int((len(_SPIKE_STENCIL) + 1) / 2)
_MIN_SLIDE = -141
_MAX_SLIDE = 201
_SMOOTH_WEIGHT = 0.65


@dataclass
class _SlideResult:
    best_slide: int
    best_score: float
    neighbor_slide: int
    neighbor_score: float
    average_score: float
    usd100_btc: float
    usd100_neighbor_btc: float
    price_usd: float
    slides_considered: int


def _place_output(counts: List[float], amount_btc: float) -> None:
    if amount_btc <= 0:
        return
    if amount_btc < 1e-6 or amount_btc > 1e5:
        return
    idx = bisect_right(_OUTPUT_BINS, amount_btc) - 1
    if idx <= 0 or idx >= _BIN_COUNT:
        return
    counts[idx] += 1.0


def _smooth_and_normalize(counts: List[float]) -> tuple[List[float], List[float]]:
    working = counts[:]

    for i in range(min(201, _BIN_COUNT)):
        working[i] = 0.0
    for i in range(1601, _BIN_COUNT):
        working[i] = 0.0

    for idx in _ROUND_BTC_BINS:
        if 0 < idx < _BIN_COUNT - 1:
            working[idx] = 0.5 * (working[idx + 1] + working[idx - 1])

    total = sum(working[201:1601])
    if total <= 0:
        raise ValueError("Not enough eligible outputs to build histogram")

    normalized = working[:]
    for i in range(201, 1601):
        value = working[i] / total
        if value > 0.008:
            value = 0.008
        normalized[i] = value

    for i in range(0, 201):
        normalized[i] = 0.0
    for i in range(1601, _BIN_COUNT):
        normalized[i] = 0.0

    return normalized, working


def _score_neighbor(counts: Sequence[float], offset: int) -> float:
    start = _LEFT_P001 + offset
    end = _RIGHT_P001 + offset
    if start < 0 or end > len(counts):
        return float("-inf")
    segment = counts[start:end]
    score = 0.0
    for idx, weight in enumerate(_SPIKE_STENCIL):
        score += segment[idx] * weight
    return score


def _slide_stencil(counts: Sequence[float]) -> _SlideResult:
    best_slide = 0
    best_score = float("-inf")
    total_score = 0.0
    slides_considered = 0

    for slide in range(_MIN_SLIDE, _MAX_SLIDE):
        start = _LEFT_P001 + slide
        end = _RIGHT_P001 + slide
        if start < 0 or end > len(counts):
            continue

        segment = counts[start:end]

        smooth_score = 0.0
        for idx, weight in enumerate(_SMOOTH_STENCIL):
            smooth_score += segment[idx] * weight

        spike_score = 0.0
        for idx, weight in enumerate(_SPIKE_STENCIL):
            spike_score += segment[idx] * weight

        if slide < 150:
            spike_score += smooth_score * _SMOOTH_WEIGHT

        if spike_score > best_score:
            best_score = spike_score
            best_slide = slide

        total_score += spike_score
        slides_considered += 1

    if slides_considered == 0 or best_score == float("-inf"):
        raise ValueError("Failed to score histogram")

    average_score = total_score / slides_considered

    neighbor_candidates = {
        +1: _score_neighbor(counts, best_slide + 1),
        -1: _score_neighbor(counts, best_slide - 1),
    }
    neighbor_slide, neighbor_score = max(neighbor_candidates.items(), key=lambda item: item[1])
    if neighbor_score == float("-inf"):
        neighbor_slide = 0
        neighbor_score = best_score

    usd100_btc = _OUTPUT_BINS[_CENTER_P001 + best_slide]
    usd100_neighbor_btc = _OUTPUT_BINS[_CENTER_P001 + best_slide + neighbor_slide]

    price_best = 100.0 / usd100_btc
    price_neighbor = 100.0 / usd100_neighbor_btc

    a1 = max(best_score - average_score, 0.0)
    a2 = max(abs(neighbor_score - average_score), 0.0)
    if a1 + a2 == 0:
        w1 = 1.0
        w2 = 0.0
    else:
        w1 = a1 / (a1 + a2)
        w2 = a2 / (a1 + a2)

    price_usd = w1 * price_best + w2 * price_neighbor

    return _SlideResult(
        best_slide=best_slide,
        best_score=best_score,
        neighbor_slide=best_slide + neighbor_slide,
        neighbor_score=neighbor_score,
        average_score=average_score,
        usd100_btc=usd100_btc,
        usd100_neighbor_btc=usd100_neighbor_btc,
        price_usd=price_usd,
        slides_considered=slides_considered,
    )


def _build_round_stats(
    normalized_counts: Sequence[float],
    raw_counts: Sequence[float],
    best_slide: int,
) -> List[RoundUsdStat]:
    stats: List[RoundUsdStat] = []
    for usd, indices in _USD_GROUPS.items():
        norm_total = 0.0
        raw_total = 0.0
        btc_weighted = 0.0
        collected_bins: List[int] = []

        for offset in indices:
            idx = offset + best_slide
            if idx <= 0 or idx >= _BIN_COUNT:
                continue
            weight_norm = normalized_counts[idx]
            weight_raw = raw_counts[idx]
            norm_total += weight_norm
            raw_total += weight_raw
            btc_weighted += _OUTPUT_BINS[idx] * weight_norm
            collected_bins.append(idx)

        if not collected_bins:
            continue

        if norm_total > 0:
            avg_btc = btc_weighted / norm_total
        else:
            avg_btc = sum(_OUTPUT_BINS[idx] for idx in collected_bins) / len(collected_bins)

        implied_price = usd / avg_btc if avg_btc > 0 else 0.0
        stats.append(
            RoundUsdStat(
                usd_amount=usd,
                bins=collected_bins,
                btc_amount=avg_btc,
                sats=int(round(avg_btc * 1e8)),
                normalized_weight=norm_total,
                raw_weight=raw_total,
                implied_price=implied_price,
            )
        )

    return stats


async def compute_stencil_price(
    rpc: Rpc,
    fulcrum: Optional[FulcrumClient],
    start_height: int,
    end_height: int,
) -> Dict[str, object]:
    counts = [0.0] * _BIN_COUNT
    txids_seen: set[str] = set()
    total_outputs = 0

    use_fulcrum = fulcrum is not None

    for height in range(start_height, end_height + 1):
        transactions: Optional[Iterable[dict]] = None
        if use_fulcrum:
            try:
                transactions = await fulcrum.get_block_transactions(height)  # type: ignore[assignment]
            except Exception as exc:
                logger.warning("Fulcrum fetch failed at height %s, falling back to RPC", height, exc_info=exc)
                use_fulcrum = False
        if transactions is None:
            block_hash = await rpc.call("getblockhash", [height])
            block = await rpc.call("getblock", [block_hash, 2])
            transactions = block.get("tx", [])  # type: ignore[arg-type]
        for tx in transactions:
            vin = tx.get("vin", [])
            vout = tx.get("vout", [])
            if not vout:
                continue
            if vin and isinstance(vin[0], dict) and "coinbase" in vin[0]:
                continue
            if len(vin) > 5 or len(vout) != 2:
                continue
            if any((out.get("scriptPubKey", {}) or {}).get("type") == "nulldata" for out in vout):
                continue

            witness_total = 0
            witness_exceeds = False
            for vin_item in vin:
                witnesses = vin_item.get("txinwitness") or []
                for witness in witnesses:
                    try:
                        data = bytes.fromhex(witness)
                    except ValueError:
                        data = b""
                    length = len(data)
                    witness_total += length
                    if length > 500 or witness_total > 500:
                        witness_exceeds = True
                        break
                if witness_exceeds:
                    break
            if witness_exceeds:
                continue

            same_day = any(vin_item.get("txid") in txids_seen for vin_item in vin if "txid" in vin_item)
            if same_day:
                continue

            for out in vout:
                value = out.get("value")
                if value is None:
                    continue
                amount = float(value)
                _place_output(counts, amount)
                total_outputs += 1

            txid = tx.get("txid")
            if isinstance(txid, str):
                txids_seen.add(txid)

    if total_outputs == 0:
        raise ValueError("No eligible outputs found in requested block range")

    normalized_counts, raw_counts = _smooth_and_normalize(counts)
    slide = _slide_stencil(normalized_counts)
    stats = _build_round_stats(normalized_counts, raw_counts, slide.best_slide)

    return {
        "samples_used": int(total_outputs),
        "estimated_price": slide.price_usd,
        "best_slide": slide.best_slide,
        "best_slide_score": slide.best_score,
        "neighbor_slide": slide.neighbor_slide,
        "neighbor_score": slide.neighbor_score,
        "average_slide_score": slide.average_score,
        "slides_considered": slide.slides_considered,
        "usd100_btc": slide.usd100_btc,
        "usd100_neighbor_btc": slide.usd100_neighbor_btc,
        "round_stats": stats,
    }
