from __future__ import annotations
import asyncio
import time
from dataclasses import dataclass, field
from typing import Deque, List, Tuple
from collections import deque

from .rpc import Rpc
from .config import SETTINGS


@dataclass
class TxOut:
    ts: float        # unix seconds when cached
    value_btc: float # output value in BTC


@dataclass
class MempoolCache:
    # Keep a rolling window of outputs (BTC values) with timestamps
    outputs: Deque[TxOut] = field(default_factory=lambda: deque(maxlen=500_000))
    last_scan_ts: float = 0.0

    def prune(self, now: float | None = None) -> None:
        now = now or time.time()
        cutoff = now - SETTINGS.lookback_sec
        while self.outputs and self.outputs[0].ts < cutoff:
            self.outputs.popleft()

    def add_outputs(self, values_btc: List[float], now: float | None = None) -> None:
        now = now or time.time()
        for v in values_btc:
            self.outputs.append(TxOut(ts=now, value_btc=v))

    def get_recent_outputs(self) -> List[float]:
        self.prune()
        return [x.value_btc for x in self.outputs]

    async def scan_once(self, rpc: Rpc) -> Tuple[int, int]:
        """
        Grab mempool txids, decode up to decode_per_tick txs, cache all vouts in BTC.
        Returns (decoded_txs, vouts_added)
        """
        txids = await rpc.call("getrawmempool", [True])  # verbose
        # Sort newest first based on "time" when available
        sorted_ids = sorted(txids.items(), key=lambda kv: kv[1].get("time", 0), reverse=True)
        to_decode = SETTINGS.decode_per_tick
        dec = 0
        added = 0
        now = time.time()

        for txid, meta in sorted_ids:
            if dec >= to_decode:
                break
            try:
                raw = await rpc.call("getrawtransaction", [txid, True])
                vouts = raw.get("vout", [])
                values = []
                for o in vouts:
                    val = o.get("value")
                    if isinstance(val, (int, float)):
                        values.append(float(val))  # BTC
                if values:
                    self.add_outputs(values, now=now)
                    added += len(values)
                dec += 1
            except Exception:
                # ignore individual tx failures
                continue

        self.last_scan_ts = now
        self.prune(now)
        return dec, added

    async def run(self, rpc: Rpc, stop_evt: asyncio.Event) -> None:
        while not stop_evt.is_set():
            try:
                await self.scan_once(rpc)
            except Exception:
                # swallow and continue; rely on logs in main loop
                pass
            await asyncio.sleep(SETTINGS.scan_interval)
