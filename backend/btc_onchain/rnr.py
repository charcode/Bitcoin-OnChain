from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Dict
import math
import statistics

from .config import SETTINGS


@dataclass
class RnrResult:
    # grid results
    grid_prices: List[float]
    raw_scores: List[float]
    zscores: List[float]
    best_price: float
    best_score: float
    confidence: float
    fwhm_usd: float
    prominence: float


def _nearest_bucket_usd(x_usd: float, step: float) -> float:
    return round(x_usd / step) * step


def _gaussian_weight(delta: float, sigma: float) -> float:
    # exp(-0.5 * (delta/sigma)^2)
    s = sigma if sigma > 1e-9 else 1e-9
    z = delta / s
    return math.exp(-0.5 * z * z)


def rnr_histogram_usd(outputs_btc: List[float], price_usd: float, step: float,
                      min_usd: float, max_usd: float) -> Dict[float, int]:
    """
    Snap each output*price_usd (=> USD) to nearest 'round-dollar bucket' (step USD).
    Only keep buckets within [min_usd, max_usd].
    """
    buckets: Dict[float, int] = {}
    for v_btc in outputs_btc:
        usd = v_btc * price_usd
        if usd < min_usd or usd > max_usd:
            continue
        b = _nearest_bucket_usd(usd, step)
        buckets[b] = buckets.get(b, 0) + 1
    return dict(sorted(buckets.items()))


def rnr_search(outputs_btc: List[float]) -> RnrResult:
    """
    For candidate prices in the USD grid, compute resonance score:
      - Convert each output value to USD with candidate price p
      - Compute distance to nearest bucket (round-dollar multiple of PRICE_STEP)
      - Score = mean over outputs of Gaussian(delta_usd; sigma_usd)
    Then robustly normalize (median/MAD) to z-scores.
    """
    step = SETTINGS.price_step
    sigma = SETTINGS.sigma_usd
    pmin, pmax = SETTINGS.price_min, SETTINGS.price_max

    if not outputs_btc:
        grid = [p for p in _frange(pmin, pmax, step)]
        zeros = [0.0 for _ in grid]
        return RnrResult(grid, zeros, zeros, grid[0], 0.0, 0.0, float("inf"), 0.0)

    grid: List[float] = [p for p in _frange(pmin, pmax, step)]
    raw_scores: List[float] = []

    inv_n = 1.0 / len(outputs_btc)

    for p in grid:
        s = 0.0
        for v_btc in outputs_btc:
            usd = v_btc * p
            nearest = _nearest_bucket_usd(usd, step)
            delta = usd - nearest
            w = _gaussian_weight(delta, sigma)
            s += w
        raw_scores.append(s * inv_n)  # mean kernel value

    # Robust normalization: median + MAD
    med = statistics.median(raw_scores)
    abs_dev = [abs(x - med) for x in raw_scores]
    mad = statistics.median(abs_dev) if any(abs_dev) else 0.0
    scale = (1.4826 * mad) if mad > 1e-12 else (statistics.pstdev(raw_scores) or 1.0)

    zscores: List[float] = [(x - med) / scale for x in raw_scores]

    # find peak
    best_idx = max(range(len(zscores)), key=lambda i: zscores[i])
    best_price = grid[best_idx]
    best_score = zscores[best_idx]

    # confidence components
    # 1) peak height (z)
    peak_height = max(0.0, best_score)

    # 2) prominence: gap vs second-highest
    second = max([zscores[i] for i in range(len(zscores)) if i != best_idx], default=med)
    prominence = max(0.0, best_score - second)

    # 3) sharpness via FWHM on raw_scores (not z), converted to USD width
    fwhm_usd = _estimate_fwhm(grid, raw_scores, best_idx)

    # Combine:
    # - peak height contributes via logistic; strong z (>=3) ~ 0.95
    # - prominence contributes; gap >= 1.5 z ~ strong
    # - sharpness: narrower fwhm → higher confidence. Normalize by a reasonable width (e.g., 20 * step)
    c_peak = _sigmoid(peak_height / 3.0)
    c_prom = _sigmoid(prominence / 1.5)
    c_sharp = 1.0 - min(1.0, (fwhm_usd / max(step * 20.0, 1e-9)))  # 0..1

    confidence = max(0.0, min(1.0, 0.5 * c_peak + 0.3 * c_prom + 0.2 * c_sharp))

    return RnrResult(
        grid_prices=grid,
        raw_scores=raw_scores,
        zscores=zscores,
        best_price=best_price,
        best_score=best_score,
        confidence=confidence,
        fwhm_usd=fwhm_usd,
        prominence=prominence,
    )


def _frange(start: float, stop: float, step: float):
    x = start
    # inclusive of stop if close
    while x <= stop + 1e-9:
        yield round(x, 8)
        x += step


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _estimate_fwhm(grid: List[float], y: List[float], idx: int) -> float:
    """
    Approximate Full Width at Half Maximum around peak index.
    Operates on raw scores (y).
    """
    peak = y[idx]
    if peak <= 0:
        return float("inf")
    half = peak * 0.5
    # left
    li = idx
    while li > 0 and y[li] >= half:
        li -= 1
    # right
    ri = idx
    n = len(y)
    while ri < n - 1 and y[ri] >= half:
        ri += 1
    if li == idx and ri == idx:
        return float("inf")
    width_points = max(1, (ri - li))
    step = SETTINGS.price_step
    return width_points * step
