from __future__ import annotations

import time
from dataclasses import dataclass, field
import math
from typing import Dict, Iterable, List, Sequence, Tuple

from ..config import SETTINGS
from ..rpc import Rpc
from .mempool_cache import TxOut

SATS_PER_BTC = 100_000_000


@dataclass
class DistributionSnapshot:
    ts: float
    bins: List[int]
    weights: List[float]
    total_samples: int
    overflow: bool
    bin_size: int
    bin_count: int
    weighted: bool
    edges: List[int] | None = None  # optional explicit edges for variable-width bins
    block_start: int | None = None
    block_end: int | None = None
    block_count: int | None = None


@dataclass
class DistributionEngine:
    block_cache: Dict[Tuple[int, int, int, int, bool], DistributionSnapshot] = field(default_factory=dict)
    cache_ttl: float = 30.0

    @staticmethod
    def _normalize_params(bin_size_sats: int, bin_count: int) -> Tuple[int, int]:
        bin_size = max(1, int(bin_size_sats))
        count = max(1, int(bin_count))
        return bin_size, count

    @staticmethod
    def _compute_distribution(samples: Iterable[Tuple[int, float]], bin_size: int, bin_count: int) -> Tuple[List[int], List[float], int, bool]:
        bins = [0 for _ in range(bin_count)]
        weights = [0.0 for _ in range(bin_count)]
        total = 0
        overflow = False

        for sats, weight in samples:
            if sats < 0:
                continue
            total += 1
            idx = sats // bin_size
            if idx >= bin_count:
                overflow = True
                idx = bin_count - 1
            bins[idx] += 1
            weights[idx] += float(weight)

        return bins, weights, total, overflow

    @staticmethod
    def _compute_distribution_edges(
        samples: Iterable[Tuple[int, float]], edges: List[int]
    ) -> Tuple[List[int], List[float], int, bool]:
        # edges define bin boundaries; bins are [edges[i], edges[i+1]) except last which is inclusive
        if not edges or len(edges) < 2:
            return [], [], 0, False
        bin_count = len(edges) - 1
        bins = [0 for _ in range(bin_count)]
        weights = [0.0 for _ in range(bin_count)]
        total = 0
        overflow = False
        for sats, weight in samples:
            if sats < 0:
                continue
            total += 1
            # find right bin via binary search
            lo, hi = 0, bin_count - 1
            idx = None
            while lo <= hi:
                mid = (lo + hi) // 2
                if edges[mid] <= sats < edges[mid + 1]:
                    idx = mid
                    break
                if sats >= edges[mid + 1]:
                    lo = mid + 1
                else:
                    hi = mid - 1
            if idx is None:
                if sats >= edges[-1]:
                    idx = bin_count - 1
                    overflow = True
                else:
                    overflow = True
                    continue
            bins[idx] += 1
            weights[idx] += float(weight)
        return bins, weights, total, overflow

    def mempool_distribution(
        self,
        outputs: Sequence[TxOut],
        *,
        bin_size_sats: int,
        bin_count: int,
        weighted: bool,
        edges: List[int] | None = None,
    ) -> DistributionSnapshot:
        bin_size, count = self._normalize_params(bin_size_sats, bin_count)
        samples = ((int(round(out.value_btc * SATS_PER_BTC)), out.weight if weighted else 1.0) for out in outputs)
        if edges and len(edges) >= 2:
            bins, weights, total, overflow = self._compute_distribution_edges(samples, edges)
        else:
            # fallback to linear buckets
            bins, weights, total, overflow = self._compute_distribution(samples, bin_size, count)
            # synthesize edges for convenience
            edges = [i * bin_size for i in range(count + 1)]
        return DistributionSnapshot(
            ts=time.time(),
            bins=bins,
            weights=weights,
            total_samples=total,
            overflow=overflow,
            bin_size=bin_size,
            bin_count=count,
            weighted=weighted,
            edges=edges,
        )

    async def block_distribution(
        self,
        rpc: Rpc,
        *,
        block_lookback: int,
        bin_size_sats: int,
        bin_count: int,
        edges: List[int] | None = None,
    ) -> DistributionSnapshot:
        bin_size, count = self._normalize_params(bin_size_sats, bin_count)
        tip_height = int(await rpc.call("getblockcount"))
        block_count = max(1, min(int(block_lookback), SETTINGS.distribution_block_max))
        block_end = tip_height
        block_start = max(0, tip_height - block_count + 1)
        cache_key = (block_start, block_end, bin_size, count, False)

        snapshot = self.block_cache.get(cache_key)
        now = time.time()
        if snapshot and now - snapshot.ts <= self.cache_ttl:
            return snapshot

        samples: List[Tuple[int, float]] = []
        for height in range(block_start, block_end + 1):
            block_hash = await rpc.call("getblockhash", [height])
            try:
                block = await rpc.call("getblock", [block_hash, 2])
            except Exception as exc:  # pragma: no cover - I/O path
                # On large responses some nodes close early; propagate for caller to decide.
                raise RuntimeError(f"getblock failed at height {height}: {exc}") from exc

            txs = block.get("tx", []) if isinstance(block, dict) else []
            for tx in txs:
                vouts = tx.get("vout", []) if isinstance(tx, dict) else []
                for vout in vouts:
                    val = vout.get("value") if isinstance(vout, dict) else None
                    if isinstance(val, (int, float)):
                        sats = int(round(float(val) * SATS_PER_BTC))
                        if sats > 0:
                            samples.append((sats, 1.0))

        if edges and len(edges) >= 2:
            bins, weights, total, overflow = self._compute_distribution_edges(samples, edges)
        else:
            bins, weights, total, overflow = self._compute_distribution(samples, bin_size, count)
            edges = [i * bin_size for i in range(count + 1)]
        snapshot = DistributionSnapshot(
            ts=now,
            bins=bins,
            weights=weights,
            total_samples=total,
            overflow=overflow,
            bin_size=bin_size,
            bin_count=count,
            weighted=False,
            edges=edges,
            block_start=block_start,
            block_end=block_end,
            block_count=block_end - block_start + 1,
        )
        self.block_cache[cache_key] = snapshot
        # Trim cache if it grows large
        if len(self.block_cache) > 16:
            # Remove oldest entry
            oldest_key = min(self.block_cache, key=lambda k: self.block_cache[k].ts)
            self.block_cache.pop(oldest_key, None)
        return snapshot


