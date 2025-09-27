from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from ..config import SETTINGS
from ..models import PriceEstimate
from ..rpc import Rpc
from .mempool_cache import MempoolCache
from .rnr_engine import RnrEngine


@dataclass
class AppState:
    rpc: Rpc
    mempool: MempoolCache = field(default_factory=MempoolCache)
    rnr: RnrEngine = field(default_factory=RnrEngine)
    stop_evt: asyncio.Event = field(default_factory=asyncio.Event)

    async def refresh_loop(self) -> None:
        await self.mempool.run(self.rpc, self.stop_evt)

    async def rnr_loop(self) -> None:
        await self.rnr.run_loop(self.mempool.get_recent_outputs, self.stop_evt)

    def latest_price_now(self) -> PriceEstimate:
        """
        Safe getter for the latest estimate; returns a default when not ready.
        """
        if self.rnr.last_result is None or self.rnr.ema_price is None:
            return PriceEstimate(t=0.0, price=0.0, confidence=0.0, curvature=0.0, samples_used=len(self.mempool.outputs))
        # compute confidence again on demand in case client calls quickly
        conf = self.rnr.compute_confidence(self.rnr.last_result)
        return PriceEstimate(
            t=float(self.rnr.last_run_ts),
            price=float(self.rnr.ema_price),
            confidence=float(conf),
            curvature=float(self.rnr.last_result.curvature),
            samples_used=len(self.mempool.outputs),
        )
