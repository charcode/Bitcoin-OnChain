from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..config import SETTINGS
from ..models import PriceEstimate
from ..rnr import rnr_search, rnr_histogram_usd, SearchResult


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass
class RnrEngine:
    last_result: Optional[SearchResult] = None
    ema_price: Optional[float] = None
    hist_cache: Dict[int, List[dict]] = field(default_factory=dict)  # grid -> bins list
    last_run_ts: float = 0.0

    def compute_confidence(self, res: SearchResult) -> float:
        z = np.asarray(res.scores, dtype=float)
        if len(z) < 5:
            return 0.0

        peak = float(z[res.best_idx])
        if peak <= 0:
            return 0.0

        pos = z[z > 0]
        med = float(np.median(pos)) if pos.size else 0.0
        denom = med if med > 1e-9 else (float(np.mean(z)) + 1e-9)
        c_peak = _sigmoid((peak / (denom + 1e-12)) - 1.0)

        mask = np.ones_like(z, dtype=bool)
        mask[max(0, res.best_idx - 2):min(len(z), res.best_idx + 3)] = False
        others = z[mask]
        second = float(np.max(others)) if others.size else 0.0
        gap = max(0.0, peak - second)
        c_prom = _sigmoid((gap / (denom + 1e-12)))

        left = max(0, res.best_idx - 3)
        right = min(len(z), res.best_idx + 4)
        local = float(np.sum(z[left:right]))
        total = float(np.sum(z)) + 1e-12
        frac = local / total
        c_sharp = max(0.0, min(1.0, frac))

        curv = float(res.curvature)
        c_curv = _sigmoid(curv / 5.0)

        conf = (0.45 * c_peak) + (0.30 * c_prom) + (0.15 * c_sharp) + (0.10 * c_curv)
        return float(max(0.0, min(1.0, conf)))

    def update_hist_cache(self, outs: List[dict], price: float) -> None:
        for g in SETTINGS.rnr_grids[:4]:
            half = SETTINGS.hist_sigma_frac * float(g)
            self.hist_cache[g] = rnr_histogram_usd(
                outs=outs,
                price_usd=price,
                grid=g,
                span_mults=SETTINGS.hist_span_mults,
                window_half=half,
            )

    def run_once(self, outs: List[dict]) -> Optional[PriceEstimate]:
        if len(outs) < SETTINGS.min_samples:
            if self.ema_price is not None:
                self.ema_price = (1.0 - SETTINGS.ema_alpha) * self.ema_price
            self.last_run_ts = time.time()
            return None

        res = rnr_search(
            outs=outs,
            price_min=SETTINGS.price_min,
            price_max=SETTINGS.price_max,
            price_step=SETTINGS.price_step,
            sigma_usd=SETTINGS.sigma_usd,
            grids=SETTINGS.rnr_grids,
        )
        self.last_result = res

        p = float(res.best_price)
        if self.ema_price is None:
            self.ema_price = p
        else:
            a = SETTINGS.ema_alpha
            self.ema_price = a * p + (1.0 - a) * self.ema_price

        conf = self.compute_confidence(res)
        self.update_hist_cache(outs, price=self.ema_price)

        self.last_run_ts = time.time()
        return PriceEstimate(
            t=self.last_run_ts,
            price=float(self.ema_price),
            confidence=float(conf),
            curvature=float(res.curvature),
            samples_used=len(outs),
        )

    async def run_loop(self, get_outs_callable, stop_evt: asyncio.Event) -> None:
        while not stop_evt.is_set():
            try:
                outs = get_outs_callable()
                self.run_once(outs)
            except Exception:
                pass
            await asyncio.sleep(SETTINGS.rnr_interval)
