"""Score finished experiment folders with the strict scorer (Experiments 1 and 2).

Owner: Michael Cardenas.

Reads what ``main.py`` already saves -- no model calls happen here:
    result/<experiment>/experiment.json
    result/<experiment>/target_task_responses.npz   (clean prompts, same defense)
    result/<experiment>/attack_responses.npz         (attacked prompts)
    data/<task>_<dataset>_<split>_<N>/target_data.npz and injected_data.npz

Writes, per experiment, to --out/<experiment>/:
    scored_attack.jsonl   one row per attacked case with its failure category
    scored_clean.jsonl    one row per clean case
    score_summary.json    counts and rates
and, across all experiments given, --out/summary.md with the defense x attack table.

Run from the repo root (only numpy is needed):
    python3 scripts/score_responses.py result/ollama_qwen3-8b_sst2_sst2_20_*
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "data"


def _load_scoring():
    # Load scoring.py directly so this script does not import the model
    # libraries (openai, torch, ...) that the package __init__ pulls in.
    path = REPO_ROOT / "OpenPromptInjection" / "evaluator" / "scoring.py"
    spec = importlib.util.spec_from_file_location("pi_scoring", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scoring = _load_scoring()


def _responses(path):
    # allow_pickle is needed because responses are saved as object arrays.
    # Only run this on result folders your own team produced.
    with np.load(path, allow_pickle=True) as archive:
        return [None if r is None else str(r) for r in archive["data"].tolist()]


def _labels(path):
    with np.load(path, allow_pickle=True) as archive:
        return [int(x) for x in archive["label"].tolist()]


def _data_dir(task_config, num):
    info, data = task_config["task_info"], task_config["dataset_info"]
    return DATA_DIR / f"{info['task']}_{data['dataset']}_{data['split']}_{num}"


def score_experiment(result_dir, out_root):
    result_dir = Path(result_dir)
    meta = json.loads((result_dir / "experiment.json").read_text())
    num = meta["data_num"]
    target_labels = _labels(_data_dir(meta["target_task_config"], num) / "target_data.npz")
    injected_labels = _labels(
        _data_dir(meta["injected_task_config"], num) / "injected_data.npz"
    )

    attack_rows = scoring.score_responses(
        _responses(result_dir / "attack_responses.npz"), target_labels, injected_labels
    )
    clean_rows = scoring.score_responses(
        _responses(result_dir / "target_task_responses.npz"), target_labels
    )
    summary = {
        "experiment": result_dir.name,
        "model": meta["model_config"]["model_info"]["name"],
        "attack": meta["attack_strategy"],
        "defense": meta["defense"],
        "data_num": num,
        "attacked": scoring.summarize(attack_rows),
        "clean": scoring.summarize(clean_rows),
    }

    out_dir = Path(out_root) / result_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("scored_attack.jsonl", attack_rows), ("scored_clean.jsonl", clean_rows)):
        with (out_dir / name).open("w") as stream:
            for row in rows:
                stream.write(json.dumps(row) + "\n")
    (out_dir / "score_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def _pct(value):
    return "n/a" if value is None else f"{100 * value:.1f}%"


def markdown_table(summaries):
    lines = [
        "| Defense | Attack | n | ASR (exact INJECTED) | Label-ASV (repo-style) | "
        "Attacked: success / invalid / incorrect / correct | Clean accuracy | Clean invalid |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in sorted(summaries, key=lambda s: (s["defense"], s["attack"])):
        a, c = s["attacked"], s["clean"]
        counts = " / ".join(str(a["counts"][k]) for k in scoring.CATEGORIES)
        lines.append(
            f"| {s['defense']} | {s['attack']} | {a['n']} | {_pct(a['asr_strict'])} | "
            f"{_pct(a.get('label_asv_repo_style'))} | {counts} | "
            f"{_pct(c['label_accuracy'])} | {_pct(c['invalid_rate'])} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("result_dirs", nargs="+", type=Path)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "evidence" / "scoring")
    args = parser.parse_args(argv)

    summaries = []
    for result_dir in args.result_dirs:
        if not (result_dir / "experiment.json").is_file():
            print(f"skip {result_dir}: no experiment.json (run not finished?)", file=sys.stderr)
            continue
        summaries.append(score_experiment(result_dir, args.out))
    if not summaries:
        print("No finished experiments found.", file=sys.stderr)
        return 1
    table = markdown_table(summaries)
    (args.out / "summary.md").write_text(table)
    print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main())
