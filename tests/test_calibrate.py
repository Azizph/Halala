import math
import unittest

import numpy as np

from halala.calibrate import binom_cdf, calibrate, certify, threshold
from halala.config import load_config


class BinomTest(unittest.TestCase):
    def test_known_values(self):
        self.assertAlmostEqual(binom_cdf(0, 10, 0.5), 1 / 1024)
        self.assertAlmostEqual(binom_cdf(10, 10, 0.3), 1.0)
        self.assertAlmostEqual(binom_cdf(1, 2, 0.5), 0.75)


class CertifyTest(unittest.TestCase):
    def test_threshold_lands_where_losses_start(self):
        scores = np.linspace(0, 1, 200)
        losses = (scores < 0.5).astype(float)   # keeping anything below 0.5 loses accuracy
        t = certify(scores, losses, epsilon=0.05, delta=0.1)
        self.assertTrue(0.4 < t <= 0.5, t)

    def test_too_few_items_certify_nothing(self):
        # With epsilon 0.05 and delta 0.1, even zero losses on 20 items prove nothing.
        self.assertTrue(math.isinf(certify(np.ones(20), np.zeros(20), 0.05, 0.1)))

    def test_small_variant_groups_escalate(self):
        cfg = load_config()
        records = [{"detected_variant": "en", "large_correct": True, "majority_correct": True}] * 100
        records += [{"detected_variant": "arabizi", "large_correct": True, "majority_correct": True}] * 10
        th = calibrate(records, np.ones(len(records)), cfg)
        self.assertIsNotNone(th["per_variant"]["en"])
        self.assertIsNone(th["per_variant"]["arabizi"])
        self.assertTrue(math.isinf(threshold(th, "arabizi")))
        self.assertTrue(math.isinf(threshold(th, "a-variant-never-seen")))


if __name__ == "__main__":
    unittest.main()
