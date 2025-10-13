from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from typing import Optional

from ..config import SETTINGS
from ..models import PriceEstimate
from ..rpc import Rpc
from .fulcrum_client import FulcrumClient
from .mempool_cache import MempoolCache
from .rnr_engine import RnrEngine
from .distribution_engine import DistributionEngine


@dataclass
class AppState:
    rpc: Rpc
    fulcrum: Optional[FulcrumClient] = None
    mempool: MempoolCache = field(default_factory=MempoolCache)
    rnr: RnrEngine = field(default_factory=RnrEngine)
    distributions: DistributionEngine = field(default_factory=DistributionEngine)
    stop_evt: asyncio.Event = field(default_factory=asyncio.Event)
    # Cached stencil for last-N blocks
    stencil_estimated_price: Optional[float] = None
    stencil_cache: Optional[dict] = None
    stencil_cache_start: Optional[int] = None
    stencil_cache_end: Optional[int] = None
    stencil_cache_ts: float = 0.0

    async def refresh_loop(self) -> None:
        await self.mempool.run(self.rpc, self.stop_evt)

    async def rnr_loop(self) -> None:
        await self.rnr.run_loop(self.mempool.get_recent_outputs, self.stop_evt)

    async def stencil_loop(self, lookback_blocks: int = 144, interval_sec: float = 180.0) -> None:
        from .stencil_price import compute_stencil_price
        while not self.stop_evt.is_set():
            try:
                tip_height = int(await self.rpc.call("getblockcount"))
                start_h = max(0, tip_height - int(abs(lookback_blocks)) + 1)
                end_h = tip_height
                result = await compute_stencil_price(self.rpc, self.fulcrum, start_h, end_h)
                self.stencil_cache = {
                    "start_height": start_h,
                    "end_height": end_h,
                    "block_count": (end_h - start_h + 1),
                    **result,
                }
                self.stencil_estimated_price = float(result.get("estimated_price", 0.0))
                self.stencil_cache_start = start_h
                self.stencil_cache_end = end_h
                self.stencil_cache_ts = asyncio.get_event_loop().time()
            except Exception:
                pass
            try:
                await asyncio.wait_for(self.stop_evt.wait(), timeout=interval_sec)
            except asyncio.TimeoutError:
                continue

    def latest_price_now(self) -> PriceEstimate:
        """
        Safe getter for the latest estimate; returns a default when not ready.
        """
        if self.rnr.ema_price is None:
            return PriceEstimate(
                t=0.0,
                price=0.0,
                confidence=0.0,
                curvature=0.0,
                samples_used=len(self.mempool.outputs),
            )
        return PriceEstimate(
            t=float(self.rnr.last_run_ts),
            price=float(self.rnr.ema_price),
            confidence=float(self.rnr.last_confidence or 0.0),
            curvature=float(self.rnr.last_curvature or 0.0),
            samples_used=int(self.rnr.last_samples_used),
        )


