"""Shadow raw-amount refinement. No network, exchange prices, or mutable state.

The coarse stencil selects a local search region, not a calibrated final price.
The band describes sensitivity to kernel width, not a coverage probability.
"""
import math
import numpy as np

VERSION = 'raw-anchor-kde-v1-shadow'
ANCHORS = np.array([5, 10, 15, 20, 25, 30, 40, 50, 100, 150, 200, 300, 500, 1000], dtype=float)
SEARCH_LOG_RADIUS = math.log(1.04)
WIDTHS = (0.0015, 0.003, 0.006)
MIN_EFFECTIVE_OUTPUTS = 30
MIN_LOCAL_SUPPORT = 0.10


def weighted_quantile(values, weights, q):
    order = np.argsort(values)
    x, w = values[order], weights[order]
    return float(x[min(np.searchsorted(np.cumsum(w), q * np.sum(w)), len(x) - 1)])


def refine(outputs, coarse_price, price_min=20000, price_max=120000):
    result = {'version': VERSION, 'status': 'insufficient', 'price': None,
              'lower': None, 'upper': None, 'band_kind': 'model_sensitivity_not_confidence_interval',
              'effective_outputs': 0., 'matched_outputs': 0, 'anchor_count': 0,
              'reason': 'Insufficient non-round output evidence'}
    if not coarse_price or not math.isfinite(coarse_price) or not price_min <= coarse_price <= price_max:
        return {**result, 'reason': 'Invalid coarse search seed'}
    rows = np.asarray(list(outputs), dtype=float)
    if rows.size == 0:
        return result
    if rows.ndim != 2 or rows.shape[1] != 2:
        raise ValueError('Expected BTC value / weight pairs')
    values, weights = rows[:, 0], rows[:, 1]
    valid = np.isfinite(values) & np.isfinite(weights) & (values > 1e-5) & (values < 1e5) & (weights > 0)
    values, weights = values[valid], weights[valid]
    sats = np.rint(values * 1e8)
    # Remove exact 1,000-satoshi multiples as a documented round-BTC artifact
    # filter. This can also remove genuine payments; never claim independence.
    mask = (np.remainder(sats, 1000) != 0)
    values, weights = values[mask], weights[mask]
    if len(values) == 0:
        return result
    implied = ANCHORS[None, :] / values[:, None]
    distance = np.abs(np.log(implied / coarse_price))
    closest = np.argmin(distance, axis=1)
    selected = implied[np.arange(len(values)), closest]
    matched = (distance[np.arange(len(values)), closest] <= SEARCH_LOG_RADIUS) & (selected >= price_min) & (selected <= price_max)
    x = implied[np.arange(len(values)), closest][matched]
    w = weights[matched]
    anchor_ids = closest[matched]
    result.update(matched_outputs=len(x), anchor_count=len(set(anchor_ids.tolist())))
    if not len(x):
        return result
    effective = float(w.sum() ** 2 / np.sum(w ** 2))
    result['effective_outputs'] = effective
    if effective < MIN_EFFECTIVE_OUTPUTS or result['anchor_count'] < 3:
        return result
    low = max(math.log(price_min), math.log(coarse_price) - SEARCH_LOG_RADIUS)
    high = min(math.log(price_max), math.log(coarse_price) + SEARCH_LOG_RADIUS)
    grid = np.linspace(low, high, 161)
    logs = np.log(x)
    modes, supports = [], []
    for width in WIDTHS:
        score = np.zeros(len(grid))
        for start in range(0, len(x), 512):
            delta = (logs[start:start+512, None] - grid[None, :]) / width
            score += np.sum(np.exp(-0.5 * delta ** 2) * w[start:start+512, None], axis=0)
        index = int(np.argmax(score))
        if index < 2 or index >= len(grid) - 2:
            return {**result, 'status': 'ambiguous', 'reason': 'Mode at search boundary'}
        # Flag a distinct competing mode with almost the same support.
        outside = np.abs(grid - grid[index]) > max(0.01, 2 * width)
        if np.any(outside) and np.max(score[outside]) >= .9 * score[index]:
            return {**result, 'status': 'ambiguous', 'reason': 'Competing implied-price modes'}
        left = right = index
        while left > 0 and score[left - 1] >= .8 * score[index]: left -= 1
        while right < len(grid) - 1 and score[right + 1] >= .8 * score[index]: right += 1
        modes.append(float(grid[index])); supports.extend([float(grid[left]), float(grid[right])])
    center = modes[1]
    local = np.abs(logs - center) <= WIDTHS[1]
    share = float(w[local].sum() / w.sum())
    sample_share = float(w[local].sum() / weights.sum())
    if share < MIN_LOCAL_SUPPORT:
        return {**result, 'status': 'ambiguous', 'reason': 'Too little local support among matched implied prices'}
    price = weighted_quantile(x[local], w[local], .5)
    lower, upper = min(math.exp(min(supports)), price), max(math.exp(max(supports)), price)
    return {**result, 'status': 'experimental', 'reason': 'Shadow candidate; not prospectively validated',
            'price': price, 'lower': lower, 'upper': upper, 'local_support_fraction': share, 'full_sample_support_fraction': sample_share,
            'kernel_widths_log': list(WIDTHS)}
