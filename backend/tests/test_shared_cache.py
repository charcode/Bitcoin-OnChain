import asyncio
import tempfile
import unittest
from pathlib import Path
from btc_onchain.core.shared_cache import SharedCache

class SharedTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_viewers_and_restart_share_result(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cache.sqlite'
            cache = SharedCache(path)
            calls = 0
            async def calculate():
                nonlocal calls
                calls += 1
                await asyncio.sleep(.01)
                return {'price': 123, 'round_stats': []}
            values = await asyncio.gather(*(cache.obtain('range:hash', calculate) for _ in range(20)))
            self.assertEqual(calls, 1)
            self.assertTrue(all(value == values[0] for value in values))
            restored = SharedCache(path)
            self.assertEqual(await restored.obtain('range:hash', calculate), values[0])
            self.assertEqual(calls, 1)
            await restored.obtain('range:reorg', calculate)
            self.assertEqual(calls, 2)
            cache.db().close()
            restored.db().close()

    async def test_failure_retries_and_storage_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = SharedCache(Path(folder) / 'cache.sqlite')
            async def fail():
                raise RuntimeError('temporary')
            with self.assertRaises(RuntimeError):
                await cache.obtain('bad', fail)
            self.assertIsNone(cache.get('bad'))
            for n in range(10):
                cache.put(str(n), {'n': n}, limit=3)
            self.assertEqual(cache.db().execute('SELECT COUNT(*) FROM cache').fetchone()[0], 3)
            cache.db().close()

    async def test_app_range_coalescing_and_block_outputs_survive_restart(self):
        import os
        from unittest.mock import AsyncMock, patch
        from btc_onchain.core.app_state import AppState
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, MODEL_CACHE_DB=str(Path(folder) / 'cache.sqlite')):
            rpc = AsyncMock()
            async def call(method, params=None):
                if method == 'getblockhash':
                    return 'canonical'
                return {'hash': 'canonical', 'tx': [{'vout': [{'value': .001}]}], 'time': 123}
            rpc.call.side_effect = call
            state = AppState(rpc)
            calculate = AsyncMock(return_value={'estimated_price': 50000, 'round_stats': []})
            with patch('btc_onchain.core.stencil_price.compute_stencil_price', calculate):
                await asyncio.gather(*(state.shared_stencil(1, 2, 'canonical') for _ in range(10)))
                await state.shared_stencil(2, 2, 'canonical')
                await state.shared_stencil(1, 2, 'canonical')
                self.assertEqual(calculate.await_count, 2)
            await asyncio.gather(*(state.block_outputs(2) for _ in range(10)))
            self.assertEqual(sum(c.args[0] == 'getblock' for c in rpc.call.await_args_list), 1)
            restored = AppState(rpc)
            self.assertEqual(await restored.block_outputs(2), {'time': 123, 'values': [.001]})
            self.assertEqual(sum(c.args[0] == 'getblock' for c in rpc.call.await_args_list), 1)
            state.shared.db().close()
            restored.shared.db().close()

    async def test_distribution_coalesces_and_separates_bin_edges_and_reorgs(self):
        from unittest.mock import AsyncMock
        from btc_onchain.core.distribution_engine import DistributionEngine
        rpc = AsyncMock()
        tip = 'one'
        rpc.call.side_effect = lambda method, params=None: 1 if method == 'getblockcount' else tip
        loader = AsyncMock(return_value={'values': [.00000005], 'time': 123})
        engine = DistributionEngine()
        async def request(edges):
            return await engine.block_distribution(rpc, block_lookback=1, block_loader=loader,
                                                  bin_size_sats=10, bin_count=2, edges=edges)
        values = await asyncio.gather(*(request([0, 10, 20]) for _ in range(10)))
        self.assertEqual(loader.await_count, 1)
        self.assertEqual(values[0].bins, [1, 0])
        self.assertEqual((await request([0, 2, 20])).bins, [0, 1])
        self.assertEqual(loader.await_count, 2)
        tip = 'reorg'
        await request([0, 10, 20])
        self.assertEqual(loader.await_count, 3)

    async def test_unchanged_inputs_do_not_repeat_live_inference(self):
        import os
        from unittest.mock import Mock, patch
        from btc_onchain.core.rnr_engine import RnrEngine
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, MODEL_CACHE_DB=str(Path(folder) / 'cache.sqlite')):
            engine = RnrEngine()
            engine.run_once = Mock()
            stop = asyncio.Event()
            ticks = 0
            async def tick(_):
                nonlocal ticks
                ticks += 1
                if ticks == 3:
                    stop.set()
            with patch('btc_onchain.core.rnr_engine.asyncio.sleep', tick):
                await engine.run_loop(lambda: [{'value_btc': .001, 'weight': 1}], stop)
            engine.run_once.assert_called_once()

    async def test_cold_http_view_enqueues_shared_work_and_returns_promptly(self):
        import json, os
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        from fastapi import HTTPException
        from btc_onchain.api.routes import debug_stencil_price
        from btc_onchain.core.app_state import AppState
        expected = json.loads((Path(__file__).parent / 'fixtures/stencil_reference.json').read_text())['expected']['1:2']
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, MODEL_CACHE_DB=str(Path(folder) / 'cache.sqlite')):
            rpc = AsyncMock()
            rpc.call.side_effect = lambda method, params=None: 2 if method == 'getblockcount' else 'one'
            state = AppState(rpc)
            request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(app_state=state)))
            calculate = AsyncMock(return_value=expected)
            with patch('btc_onchain.core.stencil_price.compute_stencil_price', calculate):
                with self.assertRaises(HTTPException) as error:
                    await debug_stencil_price(request, start=1, end=2)
                self.assertEqual(error.exception.status_code, 503)
                await state.shared_stencil(1, 2, 'one')
                result = await debug_stencil_price(request, start=1, end=2)
                self.assertEqual(result.estimated_price, expected['estimated_price'])
                calculate.assert_awaited_once()
                await asyncio.sleep(0)
            state.shared.db().close()

    async def test_ready_view_does_not_wait_for_different_cold_job(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = SharedCache(Path(folder) / 'cache.sqlite')
            cache.put('ready', {'price': 1})
            async def unused():
                self.fail('Cached view must not recalculate')
            async with cache.lock:
                result = await asyncio.wait_for(cache.obtain('ready', unused), timeout=.1)
            self.assertEqual(result, {'price': 1})
            cache.db().close()
