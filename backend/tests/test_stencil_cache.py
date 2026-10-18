import asyncio
import tempfile
import os
from unittest.mock import patch
import unittest
from unittest.mock import AsyncMock

from btc_onchain.core.stencil_cache import StencilBlockCache, compact_transactions
from btc_onchain.core.stencil_price import compute_stencil_price


def transaction(txid, parent='outside', values=(.001234, .002789)):
    return {'txid': txid, 'vin': [{'txid': parent}],
            'vout': [{'value': v, 'scriptPubKey': {'type': 'witness_v0_keyhash'}} for v in values]}


class BlockRpc:
    def __init__(self):
        self.hashes = {h: f'block-{h}' for h in range(1, 146)}
        self.blocks = {f'block-{h}': [transaction(f'tx-{h}')] for h in self.hashes}
        self.calls = []
        self.fail_bulk = False

    async def call(self, method, params):
        self.calls.append((method, params))
        if method == 'getblockhash':
            return self.hashes[params[0]]
        block_hash, verbosity = params
        txs = self.blocks[block_hash]
        if verbosity == 2 and self.fail_bulk:
            raise RuntimeError('bulk read unavailable')
        return {'hash': block_hash, 'nTx': len(txs),
                'tx': txs if verbosity == 2 else [tx['txid'] for tx in txs]}

    def bulk_reads(self):
        return sum(method == 'getblock' and params[1] == 2 for method, params in self.calls)


class StencilCacheTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, MODEL_CACHE_DB=os.path.join(self.temp.name, 'cache.sqlite'))
        self.env.start()
        self.addCleanup(self.env.stop)

    async def test_day_window_reuses_143_blocks_and_fetches_only_new_tip(self):
        rpc = BlockRpc()
        cache = StencilBlockCache(288)
        for h in range(1, 145):
            await cache.get(rpc, None, h)
        self.assertEqual(rpc.bulk_reads(), 144)
        for h in range(2, 146):
            await cache.get(rpc, None, h)
        self.assertEqual(rpc.bulk_reads(), 145)

    async def test_reorganization_at_same_height_replaces_inputs(self):
        rpc = BlockRpc()
        cache = StencilBlockCache()
        old = await cache.get(rpc, None, 1)
        rpc.hashes[1] = 'replacement'
        rpc.blocks['replacement'] = [transaction('new', values=(.003, .004))]
        new = await cache.get(rpc, None, 1)
        self.assertNotEqual(old, new)
        self.assertEqual(new[0].txid, 'new')
        self.assertEqual(rpc.bulk_reads(), 2)

    async def test_concurrent_requests_share_fetch_and_cache_is_bounded(self):
        rpc = BlockRpc()
        cache = StencilBlockCache(2)
        await asyncio.gather(*(cache.get(rpc, None, 1) for _ in range(10)))
        self.assertEqual(rpc.bulk_reads(), 1)
        await cache.get(rpc, None, 2)
        await cache.get(rpc, None, 3)
        self.assertEqual(len(cache), 2)
        await cache.get(rpc, None, 1)
        self.assertEqual(rpc.bulk_reads(), 3)  # evicted RAM inputs are served from disk

    async def test_partial_fulcrum_fallback_is_not_cached(self):
        rpc = BlockRpc()
        rpc.blocks['block-1'] = [transaction('a'), transaction('b')]
        rpc.fail_bulk = True
        fulcrum = AsyncMock()
        fulcrum.get_block_transactions.return_value = [transaction('a')]
        cache = StencilBlockCache()
        with self.assertRaisesRegex(RuntimeError, 'Incomplete Fulcrum'):
            await cache.get(rpc, fulcrum, 1)
        self.assertEqual(len(cache), 0)
        fulcrum.get_block_transactions.return_value = rpc.blocks['block-1']
        self.assertEqual(len(await cache.get(rpc, fulcrum, 1)), 2)

    async def test_same_window_spend_filter_is_reapplied_for_each_range(self):
        rpc = BlockRpc()
        rpc.blocks['block-1'] = [transaction('parent')]
        rpc.blocks['block-2'] = [transaction('child', parent='parent'), transaction('other')]
        cache = StencilBlockCache()
        full = await compute_stencil_price(rpc, None, 1, 2, cache=cache)
        narrow = await compute_stencil_price(rpc, None, 2, 2, cache=cache)
        self.assertEqual(full['samples_used'], 4)
        self.assertEqual(narrow['samples_used'], 4)
        # Narrow range must include 'child'; it was excluded in the wider range.
        only_parent = await compute_stencil_price(rpc, None, 1, 1, cache=cache)
        self.assertEqual(only_parent['samples_used'], 2)
        self.assertEqual(rpc.bulk_reads(), 2)

    async def test_chain_change_during_computation_is_rejected(self):
        rpc = BlockRpc()
        original = rpc.call
        reads = 0
        async def changing(method, params):
            nonlocal reads
            if method == 'getblockhash':
                reads += 1
                if reads == 3:
                    return 'changed'
            return await original(method, params)
        rpc.call = changing
        with self.assertRaisesRegex(RuntimeError, 'Chain changed'):
            await compute_stencil_price(rpc, None, 1, 1)


class FilterTests(unittest.TestCase):
    def test_existing_local_filters_and_witness_boundary(self):
        good = transaction('good')
        boundary = transaction('boundary')
        boundary['vin'][0]['txinwitness'] = ['aa' * 500]
        oversized = transaction('oversized')
        oversized['vin'][0]['txinwitness'] = ['aa' * 501]
        cumulative = transaction('cumulative')
        cumulative['vin'][0]['txinwitness'] = ['aa' * 300, 'bb' * 201]
        coinbase = transaction('coinbase')
        coinbase['vin'] = [{'coinbase': '00'}]
        many_inputs = transaction('many')
        many_inputs['vin'] *= 6
        nulldata = transaction('data')
        nulldata['vout'][0]['scriptPubKey']['type'] = 'nulldata'
        records = compact_transactions([good, boundary, oversized, cumulative, coinbase,
                                        many_inputs, nulldata, transaction('batch', values=(1, 2, 3))])
        self.assertEqual([r.txid for r in records], ['good', 'boundary'])


if __name__ == '__main__':
    unittest.main()
