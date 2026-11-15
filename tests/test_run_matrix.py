"""DRAFT: unit tests for run.py matrix loading and validation (stdlib only).

Covers the experiment-matrix "test environments" in configs/: required keys,
type checks, defense-name validation, and experiment naming. Also checks that
every committed matrix in configs/ is valid, so a broken config fails here
before any model is queried.

Run from the repo root:
    python3 -m unittest discover -s tests -v
"""
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = _load("pi_run_test", "run.py")

VALID_MATRIX = {
    "models": ["ollama_qwen3-8b"],
    "target_datasets": ["sst2"],
    "injected_datasets": ["sst2"],
    "data_num": 20,
    "attack_strategies": ["ignore"],
    "defenses": ["no"],
}


class MatrixLoadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def _write(self, matrix):
        path = self.tmp / "matrix.json"
        path.write_text(json.dumps(matrix), encoding="utf-8")
        return path

    def test_valid_matrix_loads(self):
        self.assertEqual(run.load_matrix(self._write(VALID_MATRIX))["data_num"], 20)

    def test_missing_key_is_rejected(self):
        matrix = dict(VALID_MATRIX)
        del matrix["defenses"]
        with self.assertRaisesRegex(ValueError, "missing=\\['defenses'\\]"):
            run.load_matrix(self._write(matrix))

    def test_unknown_key_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown=\\['typo'\\]"):
            run.load_matrix(self._write({**VALID_MATRIX, "typo": 1}))

    def test_empty_list_is_rejected(self):
        for key in ("models", "target_datasets", "injected_datasets", "attack_strategies", "defenses"):
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, key):
                    run.load_matrix(self._write({**VALID_MATRIX, key: []}))

    def test_string_instead_of_list_is_rejected(self):
        with self.assertRaises(ValueError):
            run.load_matrix(self._write({**VALID_MATRIX, "defenses": "no"}))

    def test_data_num_must_be_positive_int(self):
        for bad in (0, -5, "20", 2.5):
            with self.subTest(data_num=bad):
                with self.assertRaises(ValueError):
                    run.load_matrix(self._write({**VALID_MATRIX, "data_num": bad}))


class DefenseValidationTests(unittest.TestCase):
    def test_named_defenses_are_accepted(self):
        for name in run.SUPPORTED_DEFENSES:
            with self.subTest(defense=name):
                run._validate_defense(name)

    def test_perplexity_form_is_accepted(self):
        run._validate_defense("ppl-all-0.5")
        run._validate_defense("ppl-64-1.0")

    def test_bad_perplexity_forms_are_rejected(self):
        for bad in ("ppl-0-0.5", "ppl-x-0.5", "ppl-64-abc", "ppl-64", "ppl-64-0.5-extra", "bogus"):
            with self.subTest(defense=bad):
                with self.assertRaises(ValueError):
                    run._validate_defense(bad)


class ExperimentNameTests(unittest.TestCase):
    def test_name_encodes_every_axis(self):
        exp = run.Experiment(
            model="ollama_qwen3-8b", target_dataset="sst2", injected_dataset="sst2",
            data_num=20, attack_strategy="ignore", defense="delimiters", api_key_pos=0,
        )
        self.assertEqual(exp.name, "ollama_qwen3-8b_sst2_sst2_20_ignore_delimiters")


class CommittedMatrixTests(unittest.TestCase):
    """Every matrix shipped in configs/ must load and use supported names."""

    def test_all_committed_matrices_validate(self):
        paths = sorted((REPO_ROOT / "configs").glob("experiment_matrix*.json"))
        self.assertTrue(paths, "no experiment matrices found")
        for path in paths:
            with self.subTest(matrix=path.name):
                matrix = run.load_matrix(path)
                for attack in matrix["attack_strategies"]:
                    self.assertIn(attack, run.SUPPORTED_ATTACKS)
                for defense in matrix["defenses"]:
                    run._validate_defense(defense)


if __name__ == "__main__":
    unittest.main()
