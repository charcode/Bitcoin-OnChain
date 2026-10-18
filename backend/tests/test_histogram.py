import random
import unittest

from btc_onchain.rnr import rnr_histogram_usd


def reference(outs, price, grid, span, half):
    center = round(price / grid) * grid
    bins = []
    for k in range(-span, span + 1):
        anchor = center + k * grid
        selected = [o for o in outs if abs(float(o['value_btc']) * price - anchor) <= half]
        bins.append({'price': float(anchor), 'count': len(selected),
                     'weight_sum': sum(float(o.get('weight', 1)) for o in selected)})
    return bins


class HistogramTests(unittest.TestCase):
    def test_matches_scalar_counts_weights_and_overlapping_windows(self):
        rng = random.Random(37)
        outputs = [{'value_btc': rng.random() * 2, 'weight': rng.random()} for _ in range(1000)]
        for grid, half in [(10, 2), (100, 60), (25, 0)]:
            actual = rnr_histogram_usd(outputs, 100, grid, 8, half)
            expected = reference(outputs, 100, grid, 8, half)
            for got, want in zip(actual, expected):
                self.assertEqual(got['price'], want['price'])
                self.assertEqual(got['count'], want['count'])
                self.assertAlmostEqual(got['weight_sum'], want['weight_sum'], places=11)

    def test_inclusive_boundaries_and_iterator_input(self):
        outputs = [{'value_btc': x, 'weight': .5} for x in (.9, 1, 1.1)]
        self.assertEqual(rnr_histogram_usd(iter(outputs), 100, 10, 1, 10),
                         reference(outputs, 100, 10, 1, 10))

    def test_empty_data_and_disabled_grid(self):
        self.assertEqual(rnr_histogram_usd([], 100, 0, 8, 2), [])
        self.assertTrue(all(b['count'] == 0 for b in rnr_histogram_usd([], 100, 10, 1, 2)))


if __name__ == '__main__':
    unittest.main()
