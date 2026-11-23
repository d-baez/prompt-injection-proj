"""The 100-case final split (split_offset) must not reuse the 20-case tuning cases."""
import json
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

import numpy as np

from OpenPromptInjection.tasks import Task as task_module

ROOT = Path(__file__).resolve().parents[1]
FINAL_CONFIG = ROOT / "configs" / "task_configs" / "sst2final_config.json"
TUNING_DIR = ROOT / "data" / "sentiment_analysis_sst2_validation_20"


def _fake_raw(n=400):
    # Alternating labels; text encodes the raw index so overlap is checkable.
    return [{"sentence": f"row {i}", "label": i % 2} for i in range(n)]


class SplitOffsetTest(unittest.TestCase):
    def _build(self, tmp, num, offset):
        config = json.loads(FINAL_CONFIG.read_text())
        config["dataset_info"]["split_offset"] = offset
        spec = mock.Mock(load_raw=lambda split: _fake_raw(),
                         preprocess=lambda dp: (dp["sentence"], dp["label"]))
        with mock.patch.object(task_module, "DATA_DIR", Path(tmp)), \
             mock.patch.object(task_module, "dataset_spec", return_value=spec):
            task = task_module.Task(config, num)
            path = task.get_data_saving_path()
        with np.load(path / "target_data.npz", allow_pickle=True) as a:
            target = a["data"].tolist(), a["label"].tolist()
        with np.load(path / "injected_data.npz", allow_pickle=True) as a:
            injected = a["data"].tolist()
        return path, target, injected

    def test_offset_rows_are_skipped_and_cache_dir_differs(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            p20, (t20, _), i20 = self._build(tmp, 20, 0)
            p100, (t100, l100), i100 = self._build(tmp, 100, 40)
            self.assertNotEqual(p20, p100)
            self.assertTrue(p100.name.endswith("_off40"))
            self.assertFalse(set(t20 + i20) & set(t100 + i100))
            self.assertTrue(all(int(s.split()[1]) >= 40 for s in t100 + i100))
            self.assertEqual(Counter(l100), Counter({0: 50, 1: 50}))

    def test_final_config_is_disjoint_from_real_tuning_split(self):
        offset = json.loads(FINAL_CONFIG.read_text())["dataset_info"]["split_offset"]
        final_dir = ROOT / "data" / f"sentiment_analysis_sst2_validation_100_off{offset}"
        if not (TUNING_DIR.is_dir() and final_dir.is_dir()):
            self.skipTest("SST-2 data not prepared locally")
        def texts(d):
            out = []
            for name in ("target_data.npz", "injected_data.npz"):
                with np.load(d / name, allow_pickle=True) as a:
                    out += a["data"].tolist()
            return set(out)
        self.assertFalse(texts(TUNING_DIR) & texts(final_dir))
        with np.load(final_dir / "target_data.npz", allow_pickle=True) as a:
            self.assertEqual(Counter(a["label"].tolist()), Counter({0: 50, 1: 50}))


if __name__ == "__main__":
    unittest.main()
