from __future__ import annotations
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from ..config import SETTINGS
from ..models import PriceEstimate
from ..rpc import Rpc
from .fulcrum_client import FulcrumClient
from .mempool_cache import MempoolCache
from .rnr_engine import RnrEngine
from .distribution_engine import DistributionEngine
from .stencil_cache import StencilBlockCache
from .shared_cache import SharedCache

logger = logging.getLogger(__name__)


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
    stencil_cache_end_hash: Optional[str] = None
    stencil_blocks: StencilBlockCache = field(default_factory=lambda: StencilBlockCache(SETTINGS.stencil_cache_blocks))

    shared: SharedCache = field(default_factory=SharedCache)
    stencil_jobs: dict = field(default_factory=dict)

    async def shared_stencil(self, start_h, end_h, end_hash):
        from .stencil_price import compute_stencil_price
        async def compute():
            result = await compute_stencil_price(self.rpc, self.fulcrum, start_h, end_h, cache=self.stencil_blocks)
            if await self.rpc.call('getblockhash', [end_h]) != end_hash:
                raise RuntimeError('Chain changed during stencil calculation; retry')
            return result
        key = f'stencil-v1:{start_h}:{end_h}:{end_hash}'
        task = self.stencil_jobs.get(key)
        if task is None:
            task = asyncio.create_task(self.shared.obtain(key, compute))
            self.stencil_jobs[key] = task
            def finished(done):
                self.stencil_jobs.pop(key, None)
                if not done.cancelled() and done.exception() is not None:
                    logger.warning('Shared stencil job failed: %s', done.exception())
            task.add_done_callback(finished)
        return await asyncio.shield(task)

    async def block_outputs(self, height):
        block_hash = await self.rpc.call('getblockhash', [height])
        async def fetch():
            block = await self.rpc.call('getblock', [block_hash, 2])
            if block.get('hash', block_hash) != block_hash or block.get('nTx', len(block['tx'])) != len(block['tx']):
                raise RuntimeError('Incomplete block response')
            return {'time': block.get('time', 0), 'values': [
                float(out['value']) for tx in block['tx'] for out in tx.get('vout', [])
                if isinstance(out.get('value'), (int, float)) and out['value'] > 0]}
        return await asyncio.shield(asyncio.create_task(self.shared.obtain('outputs-v1:' + block_hash, fetch)))

    async def refresh_loop(self) -> None:
        await self.mempool.run(self.rpc, self.stop_evt)

    async def rnr_loop(self) -> None:
        await self.rnr.run_loop(self.mempool.get_recent_outputs, self.stop_evt)

    async def stencil_loop(self, lookback_blocks: Optional[int] = None, interval_sec: Optional[float] = None) -> None:
        from .stencil_price import compute_stencil_price
        lookback_blocks = SETTINGS.stencil_lookback_blocks if lookback_blocks is None else lookback_blocks
        interval_sec = SETTINGS.stencil_interval_sec if interval_sec is None else interval_sec
        while not self.stop_evt.is_set():
            try:
                chain = await self.rpc.call("getblockchaininfo")
                tip_hash = chain['bestblockhash']
                tip_height = int(chain['blocks'])
                start_h = max(0, tip_height - int(abs(lookback_blocks)) + 1)
                end_h = tip_height
                if (tip_hash != self.stencil_cache_end_hash
                        or start_h != self.stencil_cache_start or end_h != self.stencil_cache_end):
                    result = await self.shared_stencil(start_h, end_h, tip_hash)
                    if await self.rpc.call('getblockhash', [end_h]) != tip_hash:
                        raise RuntimeError('Chain changed during stencil refresh; retry')
                    self.stencil_cache = {
                        "start_height": start_h,
                        "end_height": end_h,
                        "block_count": (end_h - start_h + 1),
                        **result,
                    }
                    self.stencil_estimated_price = float(result.get("estimated_price", 0.0))
                    self.stencil_cache_start = start_h
                    self.stencil_cache_end = end_h
                    self.stencil_cache_end_hash = tip_hash
                    self.stencil_cache_ts = time.time()
                    logger.info('Stencil refreshed blocks %s-%s; compact cache blocks=%s',
                                start_h, end_h, len(self.stencil_blocks))
            except Exception:
                logger.warning('Stencil refresh failed; retaining last successful result', exc_info=True)
            try:
                await asyncio.wait_for(self.stop_evt.wait(), timeout=interval_sec)
            except asyncio.TimeoutError:
                continue

    def latest_price_now(self) -> PriceEstimate:
        """
        Safe getter for the latest estimate; returns a default when not ready.
        """
        live_price = self.rnr.ema_price
        if (
            live_price is None
            or live_price < SETTINGS.price_min
            or live_price > SETTINGS.price_max
        ):
            return PriceEstimate(
                t=0.0,
                price=None,
                confidence=0.0,
                curvature=0.0,
                samples_used=len(self.mempool.outputs),
            )
        return PriceEstimate(
            t=float(self.rnr.last_run_ts),
            price=float(live_price),
            confidence=float(self.rnr.last_confidence or 0.0),
            curvature=float(self.rnr.last_curvature or 0.0),
            samples_used=int(self.rnr.last_samples_used),
        )
