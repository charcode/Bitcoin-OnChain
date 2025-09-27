from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, List

from .config import SETTINGS
from .rpc import Rpc
from .core.mempool_cache import MempoolCache
from .rnr import rnr_search, RnrResult


@dataclass
class RnrEngine:
    """
    Maintains latest RNR result with EMA smoothing on price.
    """
    last_result: Optional[RnrResult] = None
    last_price: Optional[float] = None

    def compute(self, outputs_btc: List[float]) -> RnrResult:
        res = rnr_search(outputs_btc)
        # EMA smoothing on price estimate (optional)
        if res.best_price and res.confidence > 0:
            if self.last_price is None:
                self.last_price = res.best_price
            else:
                a = SETTINGS.ema_alpha
                self.last_price = a * res.best_price + (1 - a) * self.last_price
        self.last_result = res
        return res


@dataclass
class AppState:
    rpc: Rpc
    mempool: MempoolCache = field(default_factory=MempoolCache)
    rnr: RnrEngine = field(default_factory=RnrEngine)
    stop_evt: asyncio.Event = field(default_factory=asyncio.Event)

    async def refresh_loop(self):
        """
        High-frequency mempool refresh (decoding new txouts).
        """
        await self.mempool.run(self.rpc, self.stop_evt)

    async def rnr_loop(self):
        """
        Periodically recompute RNR curve and keep the latest result.
        """
        while not self.stop_evt.is_set():
            outs = self.mempool.get_recent_outputs()
            self.rnr.compute(outs)
            await asyncio.sleep(SETTINGS.poll_interval)

    def latest_price_now(self) -> dict:
        res = self.rnr.last_result
        samples = len(self.mempool.outputs)
        if res is None or samples < SETTINGS.min_samples:
            return {
                "t": int(time.time()),
                "price": None,
                "confidence": 0.0,
                "curvature": 0.0,
                "samples_used": samples,
            }
        return {
            "t": int(time.time()),
            "price": round(res.best_price, 2),
            "confidence": round(res.confidence, 4),
            # curvature proxy: inverse FWHM (smaller width => higher curvature)
            "curvature": 0.0 if res.fwhm_usd == float("inf") else round(1.0 / max(res.fwhm_usd, 1e-9), 6),
            "samples_used": samples,
        }
