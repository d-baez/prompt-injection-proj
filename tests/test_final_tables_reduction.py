"""Tests for the ASR-reduction / clean-accuracy-change metrics in scripts/final_tables.py.

    python3 -m unittest discover -s tests -v
"""
import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pi_final_tables_test", REPO_ROOT / "scripts/final_tables.py")
tables = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tables)


def cell(exact, n=500, clean_correct=84, clean_n=100):
    return {"exact": exact, "n": n, "clean_correct": clean_correct, "clean_n": clean_n}


class NewcombeTests(unittest.TestCase):
    def test_interval_contains_point_estimate(self):
        lo, hi = tables.newcombe(490, 500, 331, 500)
        self.assertLess(lo, 0.98 - 0.662)
        self.assertGreater(hi, 0.98 - 0.662)

    def test_equal_proportions_straddle_zero(self):
        lo, hi = tables.newcombe(84, 100, 84, 100)
        self.assertLess(lo, 0)
        self.assertGreater(hi, 0)
        self.assertAlmostEqual(lo, -hi, places=9)

    def test_known_value(self):
        # Newcombe (1998) Table II example 1: 56/70 vs 48/80 -> 0.2000, CI [0.0524, 0.3339]
        lo, hi = tables.newcombe(56, 70, 48, 80)
        self.assertAlmostEqual(lo, 0.0524, places=3)
        self.assertAlmostEqual(hi, 0.3339, places=3)


class VsNoDefenseTests(unittest.TestCase):
    def setUp(self):
        self.pooled = {
            "no": cell(490, clean_correct=84),
            "delimiters": cell(331, clean_correct=90),
            "known-answer": cell(0, clean_correct=84),
            "sandwich": cell(489, clean_correct=86),
        }
        self.result = tables.vs_no_defense(self.pooled)

    def test_baseline_excluded(self):
        self.assertNotIn("no", self.result)
        self.assertEqual(set(self.result), {"delimiters", "known-answer", "sandwich"})

    def test_reduction_signs_and_values(self):
        r = self.result["delimiters"]
        self.assertAlmostEqual(r["asr_reduction_pp"], 31.8)
        self.assertAlmostEqual(r["asr_reduction_rel"], 159 / 490)
        self.assertAlmostEqual(r["clean_change_pp"], 6.0)

    def test_full_block_is_full_relative_reduction(self):
        r = self.result["known-answer"]
        self.assertAlmostEqual(r["asr_reduction_rel"], 1.0)
        self.assertAlmostEqual(r["clean_change_pp"], 0.0)

    def test_negligible_defense_ci_includes_zero(self):
        lo, hi = self.result["sandwich"]["asr_reduction_pp_ci"]
        self.assertLess(lo, 0)
        self.assertGreater(hi, 0)

    def test_missing_baseline_returns_empty(self):
        self.assertEqual(tables.vs_no_defense({"xml": cell(450)}), {})

    def test_zero_baseline_asr_has_no_relative_reduction(self):
        result = tables.vs_no_defense({"no": cell(0), "xml": cell(0)})
        self.assertIsNone(result["xml"]["asr_reduction_rel"])


if __name__ == "__main__":
    unittest.main()
