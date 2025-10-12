from __future__ import annotations
import asyncio
import time
import math
from bisect import bisect_right
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Tuple

from ..rpc import Rpc
from ..config import SETTINGS
from ..rnr import weight_output


@dataclass
class TxOut:
    ts: float          # unix seconds when cached
    value_btc: float   # output value in BTC
    weight: float      # heuristic weight (<= 1)


@dataclass
class MempoolCache:
    """
    Rolling window of decoded vouts with light weights.
    Each cached entry is a TxOut(ts, value_btc, weight).
    """
    outputs: Deque[TxOut] = field(default_factory=lambda: deque(maxlen=500_000))
    last_scan_ts: float = 0.0

    def prune(self, now: float | None = None) -> None:
        now = now or time.time()
        cutoff = now - SETTINGS.lookback_sec
        # Proper prune
        while self.outputs and self.outputs[0].ts < cutoff:
            self.outputs.popleft()

    def add_outputs(self, values_btc: List[float], weight: float, now: float | None = None) -> None:
        now = now or time.time()
        w = float(weight)
        for v in values_btc:
            self.outputs.append(TxOut(ts=now, value_btc=float(v), weight=w))

    def get_recent_outputs(self) -> List[Dict[str, float]]:
        self.prune()
        # Return dicts used by rnr.py
        return [{"value_btc": x.value_btc, "weight": x.weight} for x in self.outputs]

    async def scan_once(self, rpc: Rpc) -> Tuple[int, int]:
        """
        Grab mempool txids, decode up to decode_per_tick txs, cache all vouts in BTC.
        Returns (decoded_txs, vouts_added)
        """
        txids = await rpc.call("getrawmempool", [True])  # verbose
        # Sort newest first based on "time" when available
        sorted_ids = sorted(txids.items(), key=lambda kv: kv[1].get("time", 0), reverse=True)
        to_decode = max(0, int(SETTINGS.decode_per_tick))
        dec = 0
        added = 0
        now = time.time()

        for txid, meta in sorted_ids:
            if dec >= to_decode:
                break
            try:
                raw = await rpc.call("getrawtransaction", [txid, True])
                vouts = raw.get("vout", [])
                n_vout = len(vouts) if isinstance(vouts, list) else 1
                is_rbf = bool(meta.get("bip125-replaceable", False))
                w = weight_output(n_vout=n_vout, is_rbf=is_rbf)

                values: List[float] = []
                for o in vouts or []:
                    val = o.get("value")
                    if isinstance(val, (int, float)):
                        values.append(float(val))  # BTC

                if values:
                    self.add_outputs(values, weight=w, now=now)
                    added += len(values)
                dec += 1
            except Exception as e:
                # Log and continue on individual tx failures
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{ts}] [mempool] getrawtransaction {txid[:12]}… failed: {e!r}")
                continue

        self.last_scan_ts = now
        self.prune(now)
        # heartbeat each pass
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{ts}] [mempool] decoded={dec:4d} added_vouts={added:5d} total_cached={len(self.outputs):7d}")
        return dec, added

    def build_heatmap(self, bucket_seconds: int, max_buckets: int, bin_edges: List[int]):
        self.prune()
        bucket_seconds = max(1, int(bucket_seconds))
        max_buckets = max(1, int(max_buckets))
        edges = sorted({int(e) for e in bin_edges if int(e) >= 0})
        if not edges:
            edges = [0]
        edges = list(edges)
        now = time.time()
        current_bucket_start = math.floor(now / bucket_seconds) * bucket_seconds
        first_bucket_start = current_bucket_start - bucket_seconds * (max_buckets - 1)

        matrix = [[0 for _ in range(len(edges))] for _ in range(max_buckets)]
        overflow = False
        total = 0

        for out in reversed(self.outputs):
            ts = out.ts
            if ts < first_bucket_start:
                break
            bucket_idx = int((ts - first_bucket_start) // bucket_seconds)
            if bucket_idx < 0 or bucket_idx >= max_buckets:
                continue
            sats = int(round(out.value_btc * 100_000_000))
            total += 1
            idx = bisect_right(edges, sats) - 1
            if idx < 0:
                overflow = True
                continue
            if idx >= len(edges):
                overflow = True
                idx = len(edges) - 1
            matrix[bucket_idx][idx] += 1

        max_count = 0
        for row in matrix:
            for val in row:
                if val > max_count:
                    max_count = val

        buckets = []
        for i, counts in enumerate(matrix):
            start = first_bucket_start + i * bucket_seconds
            end = start + bucket_seconds
            buckets.append({
                "start": float(start),
                "end": float(end),
                "counts": [int(c) for c in counts],
            })

        return {
            "t": float(now),
            "bucket_seconds": bucket_seconds,
            "bin_edges": [int(e) for e in edges],
            "buckets": buckets,
            "max_count": int(max_count),
            "total_samples": int(total),
            "overflow": overflow,
        }

    async def run(self, rpc: Rpc, stop_evt: asyncio.Event) -> None:
        while not stop_evt.is_set():
            try:
                await self.scan_once(rpc)
            except Exception as e:
                ts = time.strftime("%Y-%m-%d %H:%M:%S")
                print(f"[{ts}] [mempool] scan error: {e!r}")
            await asyncio.sleep(float(SETTINGS.scan_interval))
