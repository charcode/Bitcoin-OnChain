"""Bounded immutable-block inputs for the historical estimator."""
from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable, Optional

from .shared_cache import SharedCache
from ..rpc import Rpc
from .fulcrum_client import FulcrumClient


@dataclass(frozen=True, slots=True)
class StencilTransaction:
    txid: Optional[str]
    inputs: tuple[str, ...]
    outputs: tuple[float, ...]


def compact_transactions(transactions: Iterable[dict]) -> tuple[StencilTransaction, ...]:
    """Apply block-local filters; window-dependent spend exclusions stay outside."""
    records = []
    for tx in transactions:
        vin = tx.get('vin', [])
        vout = tx.get('vout', [])
        if not vout or (vin and 'coinbase' in vin[0]):
            continue
        if len(vin) > 5 or len(vout) != 2:
            continue
        if any((out.get('scriptPubKey', {}) or {}).get('type') == 'nulldata' for out in vout):
            continue
        witness_total = 0
        witness_exceeds = False
        for item in vin:
            for witness in item.get('txinwitness') or []:
                try:
                    length = len(bytes.fromhex(witness))
                except ValueError:
                    length = 0
                witness_total += length
                if length > 500 or witness_total > 500:
                    witness_exceeds = True
                    break
            if witness_exceeds:
                break
        if witness_exceeds:
            continue
        records.append(StencilTransaction(
            txid=tx.get('txid') if isinstance(tx.get('txid'), str) else None,
            inputs=tuple(item['txid'] for item in vin if 'txid' in item),
            outputs=tuple(float(out['value']) for out in vout if out.get('value') is not None),
        ))
    return tuple(records)


class StencilBlockCache:
    def __init__(self, max_blocks: int = 288):
        self.max_blocks = max(1, int(max_blocks))
        self._blocks: OrderedDict[str, tuple[StencilTransaction, ...]] = OrderedDict()
        self._lock = asyncio.Lock()
        self.disk = SharedCache()

    def __len__(self):
        return len(self._blocks)

    async def get(self, rpc: Rpc, fulcrum: Optional[FulcrumClient], height: int):
        block_hash = await rpc.call('getblockhash', [height])
        # Serialize cache misses so background and API requests share one fetch.
        async with self._lock:
            if block_hash in self._blocks:
                self._blocks.move_to_end(block_hash)
                return self._blocks[block_hash]
            stored = self.disk.get('block-v1:' + block_hash)
            if stored is not None:
                records = tuple(StencilTransaction(item['txid'], tuple(item['inputs']), tuple(item['outputs'])) for item in stored)
                self._blocks[block_hash] = records
                while len(self._blocks) > self.max_blocks:
                    self._blocks.popitem(last=False)
                return records
            try:
                # One bulk RPC replaces thousands of per-transaction calls.
                block = await rpc.call('getblock', [block_hash, 2])
                transactions = block['tx']
                if block.get('hash', block_hash) != block_hash:
                    raise RuntimeError('Block response hash mismatch')
                if block.get('nTx', len(transactions)) != len(transactions):
                    raise RuntimeError('Incomplete block response')
            except Exception:
                if fulcrum is None:
                    raise
                metadata = await rpc.call('getblock', [block_hash, 1])
                transactions = await fulcrum.get_block_transactions(height)
                # Fulcrum's helper can omit failed transaction requests. Do not
                # turn those partial responses into long-lived cached samples.
                if [tx.get('txid') for tx in transactions] != metadata['tx']:
                    raise RuntimeError('Incomplete Fulcrum block response')
            records = compact_transactions(transactions)
            from dataclasses import asdict
            self.disk.put('block-v1:' + block_hash, [asdict(item) for item in records])
            self._blocks[block_hash] = records
            while len(self._blocks) > self.max_blocks:
                self._blocks.popitem(last=False)
            return records
