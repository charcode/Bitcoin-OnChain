import unittest
from unittest.mock import AsyncMock, patch

from btc_onchain.config import SETTINGS
from btc_onchain.core.mempool_cache import MempoolCache


class MempoolTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.cache = MempoolCache()
        self.snapshot = {'a': {'time': 990}, 'b': {'time': 995}}
        self.failures = set()
        self.rpc = AsyncMock()

        async def call(method, params):
            if method == 'getrawmempool':
                return self.snapshot
            txid = params[0]
            if txid in self.failures:
                raise RuntimeError('transaction temporarily unavailable')
            return {'vout': [{'n': 0, 'value': .001,
                             'scriptPubKey': {'address': 'fixture'}}]}

        self.rpc.call.side_effect = call
        self.clock = patch('btc_onchain.core.mempool_cache.time.time', return_value=1000)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.budget = patch.object(SETTINGS, 'decode_per_tick', 2)
        self.budget.start()
        self.addCleanup(self.budget.stop)

    def decoded_ids(self):
        return [c.args[1][0] for c in self.rpc.call.call_args_list
                if c.args[0] == 'getrawtransaction']

    async def test_unchanged_mempool_is_not_redecoded_or_duplicated(self):
        self.assertEqual(await self.cache.scan_once(self.rpc), (2, 2))
        self.assertEqual(await self.cache.scan_once(self.rpc), (0, 0))
        self.assertEqual(len(self.cache.outputs), 2)
        self.assertEqual(len(self.cache.recent_arrivals), 2)
        self.assertEqual(len(self.decoded_ids()), 2)

    async def test_budget_advances_through_unseen_backlog(self):
        self.snapshot.update({'c': {'time': 980}, 'd': {'time': 970}})
        await self.cache.scan_once(self.rpc)
        await self.cache.scan_once(self.rpc)
        self.assertEqual(set(self.decoded_ids()), {'a', 'b', 'c', 'd'})
        self.assertEqual(len(self.cache.outputs), 4)

    async def test_failures_do_not_bypass_budget_and_are_retried(self):
        self.snapshot.update({'c': {'time': 980}, 'd': {'time': 970}})
        self.failures = set(self.snapshot)
        self.assertEqual(await self.cache.scan_once(self.rpc), (0, 0))
        self.assertEqual(len(self.decoded_ids()), 2)
        self.failures.clear()
        self.assertEqual(await self.cache.scan_once(self.rpc), (2, 2))

    async def test_expired_samples_are_not_refreshed_by_unchanged_tx(self):
        await self.cache.scan_once(self.rpc)
        self.now.return_value = 2001
        self.assertEqual(await self.cache.scan_once(self.rpc), (0, 0))
        self.assertEqual(len(self.cache.outputs), 0)

    async def test_removed_tx_reappearing_in_window_does_not_duplicate(self):
        await self.cache.scan_once(self.rpc)
        original = self.snapshot
        self.snapshot = {}
        await self.cache.scan_once(self.rpc)
        self.snapshot = original
        self.assertEqual(await self.cache.scan_once(self.rpc), (0, 0))
        self.assertEqual(len(self.cache.outputs), 2)

    async def test_old_transaction_is_not_treated_as_fresh_arrival(self):
        self.snapshot = {'old': {'time': 1}, 'new': {'time': 999}}
        self.assertEqual(await self.cache.scan_once(self.rpc), (1, 1))
        self.assertEqual(self.decoded_ids(), ['new'])


if __name__ == '__main__':
    unittest.main()
