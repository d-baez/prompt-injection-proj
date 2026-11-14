"""Tests for the ``blocked`` category (defense refused the input, no model answer).

Run from the repo root:
    python3 -m unittest discover -s tests -v
"""
import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scoring = _load("pi_scoring_blocked_test", "OpenPromptInjection/evaluator/scoring.py")


class BlockedCategoryTests(unittest.TestCase):
    def test_blocked_flag_overrides_empty_response(self):
        rows = scoring.score_responses([""], [1], blocked=[True])
        self.assertEqual(rows[0]["category"], "blocked")
        self.assertTrue(rows[0]["blocked"])

    def test_blocked_is_not_counted_as_invalid(self):
        rows = scoring.score_responses(["", "positive"], [1, 1], blocked=[True, False])
        summary = scoring.summarize(rows)
        self.assertEqual(summary["counts"]["blocked"], 1)
        self.assertEqual(summary["counts"]["invalid"], 0)
        self.assertEqual(summary["blocked_rate"], 0.5)
        self.assertEqual(summary["invalid_rate"], 0.0)

    def test_blocked_still_counts_as_not_correct(self):
        rows = scoring.score_responses(["", "positive"], [1, 1], blocked=[True, False])
        self.assertEqual(scoring.summarize(rows)["label_accuracy"], 0.5)

    def test_unblocked_empty_response_stays_invalid(self):
        rows = scoring.score_responses([""], [1], blocked=[False])
        self.assertEqual(rows[0]["category"], "invalid")

    def test_no_mask_keeps_original_behaviour(self):
        rows = scoring.score_responses(["", "INJECTED"], [1, 1])
        self.assertEqual([r["category"] for r in rows], ["invalid", "attack_succeeded"])
        self.assertEqual(scoring.summarize(rows)["blocked_rate"], 0.0)

    def test_mask_must_align(self):
        with self.assertRaises(ValueError):
            scoring.score_responses(["positive"], [1], blocked=[True, False])


if __name__ == "__main__":
    unittest.main()
