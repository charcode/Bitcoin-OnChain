import asyncio
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from btc_onchain.oracle.refined import refine, ANCHORS
from btc_onchain.oracle.utxoracle_live import estimate_from_outputs
from btc_onchain.models import PriceEstimate
from btc_onchain.core.rnr_engine import RnrEngine
from btc_onchain.core.external_prices import ExternalPricePoller
from btc_onchain.core.evaluation import compare, EvaluationRecorder
from btc_onchain.api.routes_prices import router


class RefinementTests(unittest.TestCase):
    def test_known_price_refinement_reduces_bias_without_exchange_input(self):
        for price in (60000, 80000, 81992.1, 82000, 82500, 90000):
            outputs = [(round(float(a)/price*1e8)/1e8, 1.) for a in ANCHORS for _ in range(30)]
            legacy = estimate_from_outputs(outputs)
            seed = max(legacy.curve_points, key=lambda p: p[1])[0]
            candidate = refine(outputs, seed)
            with self.subTest(price=price):
                self.assertEqual(candidate['status'], 'experimental')
                self.assertLess(abs(candidate['price']/price-1), .001)
                self.assertLess(abs(candidate['price']-price), abs(legacy.price-price))
                self.assertLessEqual(candidate['lower'], candidate['price'])
                self.assertGreaterEqual(candidate['upper'], candidate['price'])

    def test_distracting_outputs_do_not_hide_a_supported_local_mode(self):
        import numpy as np
        rng = np.random.default_rng(24)
        price = 82000
        signal = [(round(float(a)/price*1e8)/1e8, 1.) for a in ANCHORS for _ in range(20)]
        noise = [(float(v), 1.) for v in np.exp(rng.uniform(math.log(.00005), math.log(.02), 3000))]
        candidate = refine(signal + noise, 82400)
        self.assertEqual(candidate['status'], 'experimental')
        self.assertLess(abs(candidate['price']/price-1), .001)

    def test_round_btc_collision_and_empty_sample_abstain(self):
        for pairs in ([], [(float(a)/100000, 1.) for a in ANCHORS for _ in range(30)]):
            result = refine(pairs, 100000)
            self.assertIsNone(result['price'])
            self.assertNotEqual(result['status'], 'experimental')

    def test_invalid_values_and_seed(self):
        self.assertIsNone(refine([(float('nan'), 1), (.001, -1)], 82000)['price'])
        self.assertIsNone(refine([(.001, 1)], float('nan'))['price'])

    def test_flat_ambiguous_signal_abstains(self):
        import numpy as np
        rng = np.random.default_rng(12)
        outputs = [(float(v), 1.) for v in np.exp(rng.uniform(math.log(.00005), math.log(.02), 3000))]
        result = refine(outputs, 82000)
        self.assertNotEqual(result['status'], 'experimental')

    def test_low_samples_hold_original_price_and_timestamp(self):
        engine = RnrEngine(ema_price=82000, last_run_ts=100.)
        with patch('btc_onchain.core.rnr_engine.SETTINGS.min_samples', 500):
            self.assertIsNone(engine.run_once([]))
        self.assertEqual(engine.ema_price, 82000)
        self.assertEqual(engine.last_run_ts, 100.)
        self.assertEqual(engine.last_status, 'insufficient')


def fake_state(now=1000):
    engine = SimpleNamespace(candidate={'price': 82000, 'lower': 81500, 'upper': 82500, 'status': 'experimental'}, candidate_ts=now, last_status='ok')
    return SimpleNamespace(rnr=engine, latest_price_now=lambda: PriceEstimate(t=now, price=82800, confidence=0., curvature=0., samples_used=500))


class EvaluationTests(unittest.TestCase):
    def poller(self, now=1000):
        poller = ExternalPricePoller(':memory:', 30, ['kraken', 'coinbase'])
        poller.quotes = {s: {'price': 82000, 'ts': now, 'status': 'ok', 'quote_currency': 'USD'} for s in poller.sources}
        return poller

    def test_signed_error_and_no_reference_no_fabricated_zero(self):
        state = fake_state()
        d = compare(state, self.poller(), 1000)
        self.assertEqual(d['legacy']['error_usd'], 800)
        self.assertEqual(d['candidate']['error_usd'], 0)
        self.assertIsNone(compare(state, None, 1000)['legacy']['error_usd'])

    def test_stale_quotes_models_and_timestamp_skew_are_not_scored(self):
        state = fake_state()
        self.assertIsNone(compare(state, self.poller(800), 1000)['legacy']['error_usd'])
        self.assertIsNone(compare(state, self.poller(), 1100)['legacy']['error_usd'])
        self.assertIsNone(compare(state, self.poller(950), 1000)['legacy']['error_usd'])
        p = self.poller(); p.quotes['kraken']['status'] = 'unavailable'
        p.quotes['coinbase']['market_ts'] = 800
        self.assertIsNone(p.snapshot(1000)['median']['price'])

    def test_comparison_routes_accept_typed_model_and_disabled_poller(self):
        app = FastAPI(); app.include_router(router)
        app.state.app_state = fake_state()
        with TestClient(app) as client:
            for path in ('/price/compare', '/price/evaluation'):
                r = client.get(path)
                self.assertEqual(r.status_code, 200)
            self.assertIsNone(client.get('/price/compare').json()['delta_pct'])


class RecorderTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistence_dedup_and_paired_coverage(self):
        import time
        with tempfile.TemporaryDirectory() as d:
            now = time.time(); state = fake_state(now)
            poller = EvaluationTests().poller(now)
            path = str(Path(d)/'evaluation.sqlite')
            recorder = EvaluationRecorder(state, poller, path)
            task = asyncio.create_task(recorder.run())
            for _ in range(100):
                if recorder.stats.get('paired_n') == 1: break
                await asyncio.sleep(.01)
            task.cancel()
            try: await task
            except asyncio.CancelledError: pass
            self.assertEqual(recorder.stats['paired_n'], 1)
            await recorder.tick()
            self.assertEqual(recorder.stats['paired_n'], 1)
            self.assertEqual(recorder.stats['paired_models']['candidate']['band_coverage_pct'], 100)
            fresh_recorder = EvaluationRecorder(state, poller, path)
            await fresh_recorder.tick()
            self.assertEqual(fresh_recorder.stats['paired_n'], 1)


if __name__ == '__main__': unittest.main()
