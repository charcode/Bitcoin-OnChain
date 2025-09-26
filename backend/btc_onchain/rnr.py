from __future__ import annotations
import math
from typing import Dict, Any, List, Tuple
from .config import settings

def round_kernel(u_usd: float, g: float, sigma: float) -> float:
    r = u_usd % g
    d = min(r, g - r) / g
    return math.exp(- (d * d) / (2 * sigma * sigma))

def rnr_score_for_price(outputs: List[Dict[str, Any]], p: float) -> float:
    s = 0.0
    for o in outputs:
        u = o["value_btc"] * p
        kmax = max(round_kernel(u, g, settings.sigma) for g in settings.grids)
        s += o.get("weight", 1.0) * kmax
    return s

def rnr_search(outputs: List[Dict[str, Any]]) -> Tuple[float | None, float, float, List[Tuple[float, float]]]:
    best_p, best_s, pts = None, -1.0, []
    p = settings.price_min
    while p <= settings.price_max:
        s = rnr_score_for_price(outputs, p)
        pts.append((p, s))
        if s > best_s:
            best_p, best_s = p, s
        p += settings.price_step
    curvature = 0.0
    if best_p is not None:
        i = [i for i, x in enumerate(pts) if x[0] == best_p][0]
        if 0 < i < len(pts) - 1:
            p1, s1 = pts[i - 1]; p2, s2 = pts[i]; p3, s3 = pts[i + 1]
            denom = (p1 - p2) * (p1 - p3) * (p2 - p3)
            if denom != 0:
                a = (p3 * (s2 - s1) + p2 * (s1 - s3) + p1 * (s3 - s2)) / denom
                curvature = -a
    return best_p, best_s, curvature, pts

def weight_output(num_outputs: int, is_rbf: bool) -> float:
    w = 1.0
    if num_outputs in (1, 2):
        w *= 1.3
    if is_rbf:
        w *= 1.2
    return w
