"""Small regression tests; full-brain equivalence is checked by --pilot."""
import json
from pathlib import Path
import unittest

import numpy as np
import pandas as pd

from analyze import metrics
from run_experiment import input_pattern, validate_protocol

P = json.loads((Path(__file__).parent / "protocols/main_v1.json").read_text())


def responses(train, probes=(10, 10)):
    return pd.DataFrame([{"phase": "train", "pulse": i, "rest_ms": 0, "aBN1": n}
                         for i, n in enumerate(train)] +
                        [{"phase": "recovery", "pulse": -1, "rest_ms": r, "aBN1": n}
                         for r, n in zip(P["recovery_ms"], probes)])


class ProtocolTests(unittest.TestCase):
    def test_canonical(self):
        validate_protocol(P)

    def test_off_grid_long_rest_rejected(self):
        p = dict(P, recovery_ms=[10000.05])
        with self.assertRaisesRegex(ValueError, "Off-grid"):
            validate_protocol(p)

    def test_overlapping_windows_rejected(self):
        with self.assertRaisesRegex(ValueError, "Overlapping"):
            validate_protocol(dict(P, onset_intervals_ms=[100.0]))

    def test_invalid_probability_rejected(self):
        with self.assertRaisesRegex(ValueError, "probability"):
            validate_protocol(dict(P, input_hz=10000))

    def test_input_replay(self):
        a, b = input_pattern(1701, 70, P), input_pattern(1701, 70, P)
        np.testing.assert_array_equal(a[0], b[0])
        np.testing.assert_array_equal(a[1], b[1])
        self.assertEqual(len(set(zip(a[0], a[1]))), len(a[0]))
        self.assertTrue(np.all(np.diff(a[1]) >= 0))
        self.assertTrue(np.all((a[0] >= 0) & (a[0] < 70)))
        self.assertTrue(np.all((a[1] >= 0) & (a[1] < P["pulse_ms"]/P["dt_ms"])))
        self.assertFalse(np.array_equal(a[1], input_pattern(1702, 70, P)[1]))


class MetricTests(unittest.TestCase):
    def test_constant_not_habituation(self):
        m = metrics(responses([10]*12), P)
        self.assertEqual(m["decrement_fraction"], 0)
        self.assertFalse(m["h1_screen"])
        self.assertFalse(m["h2_screen"])
        self.assertTrue(m["plateau_screen"])
        self.assertIsNone(m["exploratory_recovered_loss_fraction_2000"])

    def test_decrement_and_recovery(self):
        m = metrics(responses([10]*3+[6]*3+[4]*6, probes=(6, 9)), P)
        self.assertAlmostEqual(m["decrement_fraction"], 0.6)
        self.assertTrue(m["h1_screen"])
        self.assertTrue(m["h2_screen"])
        self.assertTrue(m["plateau_screen"])
        self.assertAlmostEqual(m["probe_to_initial_10000"], 0.9)

    def test_decrement_without_recovery(self):
        m = metrics(responses([10]*3+[6]*3+[4]*6, probes=(4, 4)), P)
        self.assertTrue(m["h1_screen"])
        self.assertFalse(m["h2_screen"])

    def test_zero_baseline_is_undefined(self):
        m = metrics(responses([0]*12, probes=(0, 0)), P)
        self.assertIsNone(m["decrement_fraction"])
        self.assertIsNone(m["probe_to_initial_2000"])
        self.assertFalse(m["h1_screen"])
        self.assertFalse(m["h2_screen"])

    def test_not_at_plateau(self):
        m = metrics(responses([10]*3+[8]*3+[6]*3+[2]*3), P)
        self.assertFalse(m["plateau_screen"])


if __name__ == "__main__":
    unittest.main()
