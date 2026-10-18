import asyncio
import tempfile
import os
from unittest.mock import patch
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from btc_onchain.core.app_state import AppState
from btc_onchain.core.stencil_cache import StencilBlockCache
from btc_onchain.core.stencil_price import compute_stencil_price
from test_stencil_cache import BlockRpc


FIXTURE = json.loads((Path(__file__).parent / 'fixtures/stencil_reference.json').read_text())


class RefreshTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, MODEL_CACHE_DB=os.path.join(self.temp.name, 'cache.sqlite'))
        self.env.start()
        self.addCleanup(self.env.stop)

    async def test_compact_cached_estimator_matches_original_result(self):
        rpc = BlockRpc()
        for height, transactions in FIXTURE['blocks'].items():
            rpc.blocks[f'block-{height}'] = transactions
        cache = StencilBlockCache()
        for span, expected in FIXTURE['expected'].items():
            start, end = map(int, span.split(':'))
            got = await compute_stencil_price(rpc, None, start, end, cache=cache)
            got['round_stats'] = [stat.model_dump() for stat in got['round_stats']]
            self.assertEqual(got, expected)
        self.assertEqual(rpc.bulk_reads(), 2)

    async def test_background_skips_same_tip_but_refreshes_same_height_reorg(self):
        rpc = AsyncMock()
        state = AppState(rpc)
        polls = 0
        current_hash = 'one'
        async def call(method, params=None):
            nonlocal polls, current_hash
            if method == 'getblockchaininfo':
                polls += 1
                current_hash = 'one' if polls <= 2 else 'replacement'
                if polls == 4:
                    state.stop_evt.set()
                return {'blocks': 100, 'bestblockhash': current_hash}
            return current_hash
        rpc.call.side_effect = call
        with patch('btc_onchain.core.stencil_price.compute_stencil_price',
                   new=AsyncMock(return_value={'estimated_price': 50000})) as calculate:
            await state.stencil_loop(lookback_blocks=2, interval_sec=.001)
        self.assertEqual(calculate.await_count, 2)
        self.assertEqual(state.stencil_cache_end_hash, 'replacement')

    async def test_failed_refresh_is_retried_without_poisoning_cached_tip(self):
        rpc = AsyncMock()
        state = AppState(rpc)
        polls = 0
        async def call(method, params=None):
            nonlocal polls
            if method == 'getblockchaininfo':
                polls += 1
                if polls == 3:
                    state.stop_evt.set()
                return {'blocks': 100, 'bestblockhash': 'one'}
            return 'one'
        rpc.call.side_effect = call
        calculate = AsyncMock(side_effect=[RuntimeError('temporary'), {'estimated_price': 50000}])
        with self.assertLogs('btc_onchain.core.app_state', level='WARNING'), patch(
                'btc_onchain.core.stencil_price.compute_stencil_price', new=calculate):
            await state.stencil_loop(2, .001)
        self.assertEqual(calculate.await_count, 2)
        self.assertEqual(state.stencil_cache_end_hash, 'one')

    async def test_cached_api_response_has_no_duplicate_fields_and_invalidates_reorg(self):
        from btc_onchain.api.routes import debug_stencil_price
        rpc = AsyncMock()
        rpc.call.side_effect = lambda method, params=None: 2 if method == 'getblockcount' else 'one'
        state = AppState(rpc)
        state.stencil_cache = dict(FIXTURE['expected']['1:2'], start_height=1, end_height=2, block_count=2)
        state.stencil_cache_start = 1
        state.stencil_cache_end = 2
        state.stencil_cache_end_hash = 'one'
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(app_state=state)))
        with patch('btc_onchain.core.stencil_price.compute_stencil_price', new=AsyncMock()) as calculate:
            result = await debug_stencil_price(request, start=1, end=2, wait=True)
            self.assertEqual(result.samples_used, FIXTURE['expected']['1:2']['samples_used'])
            calculate.assert_not_awaited()
        rpc.call.side_effect = lambda method, params=None: 2 if method == 'getblockcount' else 'new'
        with patch('btc_onchain.core.stencil_price.compute_stencil_price',
                   new=AsyncMock(return_value=FIXTURE['expected']['1:2'])) as calculate:
            await debug_stencil_price(request, start=1, end=2, wait=True)
            calculate.assert_awaited_once()
        self.assertEqual(state.stencil_cache_end_hash, 'new')


if __name__ == '__main__':
    unittest.main()
