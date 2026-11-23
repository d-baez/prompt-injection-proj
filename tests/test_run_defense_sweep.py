"""Tests for scripts/run_defense_sweep.py and the llama3.1:8b configs (no model calls).

    python3 -m unittest discover -s tests -v
"""
import importlib.util
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sweep = _load("pi_defense_sweep_test", "scripts/run_defense_sweep.py")
run = _load("pi_run_for_sweep_test", "run.py")

NEW_MODEL = "ollama_llama3.1-8b"


class NewModelConfigTests(unittest.TestCase):
    def test_model_config_matches_final_settings(self):
        config = json.loads(
            (REPO_ROOT / "configs/model_configs/ollama_llama3.1-8b_config.json").read_text()
        )
        self.assertEqual(config["model_info"], {"provider": "ollama", "name": "llama3.1:8b"})
        self.assertEqual(config["params"]["temperature"], 0.0)
        self.assertEqual(config["params"]["seed"], 100)
        self.assertEqual(config["params"]["max_output_tokens"], 512)

    def test_final_matrix_matches_qwen_except_model(self):
        qwen = json.loads(sweep.TEMPLATE_MATRIX.read_text())
        llama = json.loads(sweep.default_matrix_path(NEW_MODEL).read_text())
        self.assertEqual(llama["models"], [NEW_MODEL])
        qwen.pop("models"), llama.pop("models")
        self.assertEqual(llama, qwen)

    def test_final_matrix_builds_50_experiments(self):
        matrix = json.loads(sweep.default_matrix_path(NEW_MODEL).read_text())
        self.assertEqual(len(run.build_experiments(matrix)), 50)


class BuildMatrixTests(unittest.TestCase):
    def test_uses_committed_matrix_for_model(self):
        matrix, source = sweep.build_matrix(model=NEW_MODEL)
        self.assertEqual(source, sweep.default_matrix_path(NEW_MODEL).name)
        self.assertEqual(matrix["defenses"], sweep.ALL_DEFENSES)

    def test_falls_back_to_template_with_model_swapped(self):
        matrix, source = sweep.build_matrix(model="ollama_mistral_final")
        self.assertEqual(source, sweep.TEMPLATE_MATRIX.name)
        self.assertEqual(matrix["models"], ["ollama_mistral_final"])

    def test_defense_and_size_filters(self):
        matrix, _ = sweep.build_matrix(model=NEW_MODEL, defenses=["no", "known-answer"], data_num=10)
        self.assertEqual(matrix["defenses"], ["no", "known-answer"])
        self.assertEqual(matrix["data_num"], 10)
        self.assertEqual(len(run.build_experiments(matrix)), 10)

    def test_rejects_unknown_defense_and_model(self):
        with self.assertRaises(ValueError):
            sweep.build_matrix(model=NEW_MODEL, defenses=["llm-based-typo"])
        with self.assertRaises(FileNotFoundError):
            sweep.build_matrix(model="ollama_does-not-exist")


class NamingTests(unittest.TestCase):
    def test_result_dirs_match_run_py_names(self):
        matrix, _ = sweep.build_matrix(model=NEW_MODEL)
        ours = sorted(p.name for p in sweep.result_dirs_for(matrix, "/tmp/r"))
        theirs = sorted(e.name for e in run.build_experiments(matrix))
        self.assertEqual(ours, theirs)

    def test_default_out_dir(self):
        matrix, _ = sweep.build_matrix(model=NEW_MODEL)
        self.assertEqual(sweep.default_out_dir(matrix),
                         REPO_ROOT / "evidence" / "final100_llama3.1-8b")

    def test_run_command_is_sequential_and_resumable(self):
        cmd = sweep.run_command(Path("m.json"), Path("/tmp/r"), 2, dry_run=False)
        self.assertIn("--skip-completed", cmd)
        self.assertEqual(cmd[cmd.index("--max-parallel") + 1], "1")
        self.assertNotIn("--dry-run", cmd)


class DryRunTests(unittest.TestCase):
    def test_dry_run_end_to_end(self):
        self.assertEqual(sweep.main(["--model", NEW_MODEL, "--dry-run"]), 0)


if __name__ == "__main__":
    unittest.main()
