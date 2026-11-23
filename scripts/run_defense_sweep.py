"""Run the full defense sweep for one model, then score it and build the tables.

Owner: Michael Cardenas.

One command for the three steps in evidence/HANDOFF_2026-11-20.md:
  1. run.py on a 5-attack x 10-defense x N-case matrix (one Ollama request at a time)
  2. scripts/score_responses.py on the finished result folders
  3. scripts/final_tables.py on the scored folder (95% Wilson intervals)

Pass either a model config name (configs/model_configs/<name>_config.json) or a matrix file.
With --model, the matrix is the committed final100 matrix for that model if it exists, or one
built from the qwen final100 template with the model swapped in.

    # new model: full sweep, scoring and tables into evidence/final100_llama3.1-8b/
    uv run python scripts/run_defense_sweep.py --model ollama_llama3.1-8b

    # check configs and print the run.py commands, no model calls
    uv run python scripts/run_defense_sweep.py --model ollama_llama3.1-8b --dry-run

    # only some defenses (e.g. a quick check before the full run)
    uv run python scripts/run_defense_sweep.py --model ollama_llama3.1-8b \
        --defenses no known-answer --data-num 100 --out evidence/check_llama

    # rescore an existing run without querying the model again
    uv run python scripts/run_defense_sweep.py --model ollama_qwen3-8b --skip-run

Resumes like run.py: finished experiments are skipped and a crashed one restarts from its
last saved sample. Changing a model config invalidates its cached responses, so move old
result folders aside first.
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "configs"
TEMPLATE_MATRIX = CONFIG_DIR / "experiment_matrix_ollama_marker_qwen3-8b_final100.json"
ALL_DEFENSES = [
    "no", "instructional", "delimiters", "xml", "sandwich", "random_seq",
    "known-answer", "response-based", "paraphrasing", "retokenization",
]


def short_name(model):
    """ollama_llama3.1-8b -> llama3.1-8b (matches evidence/final100_<short>/)."""
    return model[len("ollama_"):] if model.startswith("ollama_") else model


def default_matrix_path(model):
    return CONFIG_DIR / f"experiment_matrix_ollama_marker_{short_name(model)}_final100.json"


def build_matrix(model=None, matrix_path=None, defenses=None, data_num=None):
    """Return (matrix dict, source description). Never writes to configs/."""
    if matrix_path is None:
        if model is None:
            raise ValueError("pass --model or --matrix")
        candidate = default_matrix_path(model)
        matrix_path = candidate if candidate.is_file() else TEMPLATE_MATRIX
    matrix = json.loads(Path(matrix_path).read_text())
    source = Path(matrix_path).name
    if model is not None:
        if not (CONFIG_DIR / "model_configs" / f"{model}_config.json").is_file():
            raise FileNotFoundError(f"no model config configs/model_configs/{model}_config.json")
        matrix["models"] = [model]
    if defenses:
        unknown = sorted(set(defenses) - set(ALL_DEFENSES))
        if unknown:
            raise ValueError(f"unknown defenses: {unknown}; choose from {ALL_DEFENSES}")
        matrix["defenses"] = list(defenses)
    if data_num is not None:
        matrix["data_num"] = data_num
    return matrix, source


def result_dirs_for(matrix, result_dir):
    """The result/<experiment> folders run.py writes for this matrix (same naming as run.py)."""
    dirs = []
    for model in matrix["models"]:
        for target in matrix["target_datasets"]:
            for injected in matrix["injected_datasets"]:
                for attack in matrix["attack_strategies"]:
                    for defense in matrix["defenses"]:
                        name = f"{model}_{target}_{injected}_{matrix['data_num']}_{attack}_{defense}"
                        dirs.append(Path(result_dir) / name)
    return dirs


def default_out_dir(matrix):
    model = matrix["models"][0]
    return REPO_ROOT / "evidence" / f"final{matrix['data_num']}_{short_name(model)}"


def run_command(matrix_file, result_dir, max_retries, dry_run):
    cmd = [
        sys.executable, str(REPO_ROOT / "run.py"),
        "--matrix-config", str(matrix_file),
        "--result-dir", str(result_dir),
        "--max-parallel", "1",
        "--max-retries", str(max_retries),
        "--skip-completed",
    ]
    if dry_run:
        cmd.append("--dry-run")
    return cmd


def check_ollama(model):
    """Return an error string if Ollama isn't serving the model, else None."""
    config = json.loads((CONFIG_DIR / "model_configs" / f"{model}_config.json").read_text())
    base = config.get("api_key_info", {}).get("base_url", "").rstrip("/")
    if ":11434" not in base:
        return None  # not a local Ollama model
    name = config["model_info"]["name"]
    tags_url = base[: -len("/v1")] + "/api/tags" if base.endswith("/v1") else base + "/api/tags"
    try:
        with urllib.request.urlopen(tags_url, timeout=5) as response:
            tags = json.load(response)
    except (urllib.error.URLError, OSError) as exc:
        return f"Ollama isn't reachable at {tags_url} ({exc}). Start it with `ollama serve`."
    served = {m.get("name") for m in tags.get("models", [])}
    if name not in served and f"{name}:latest" not in served:
        return f"Ollama doesn't have {name}. Run `ollama pull {name}` first."
    return None


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--model", help="model config name, e.g. ollama_llama3.1-8b")
    source.add_argument("--matrix", type=Path, help="experiment matrix JSON to run as is")
    parser.add_argument("--defenses", nargs="+", help=f"subset of {ALL_DEFENSES}")
    parser.add_argument("--data-num", type=int, help="cases per experiment (default: matrix's)")
    parser.add_argument("--out", type=Path, help="scored folder (default: evidence/final<N>_<model>)")
    parser.add_argument("--result-dir", type=Path, default=REPO_ROOT / "result")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true", help="print run.py commands, no model calls")
    parser.add_argument("--skip-run", action="store_true", help="only score and build tables")
    parser.add_argument("--skip-score", action="store_true", help="only run the sweep")
    parser.add_argument("--no-preflight", action="store_true", help="skip the Ollama model check")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        matrix, source = build_matrix(args.model, args.matrix, args.defenses, args.data_num)
    except (ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    out_dir = args.out or default_out_dir(matrix)
    result_dir = args.result_dir.expanduser().resolve()
    n_exp = len(result_dirs_for(matrix, result_dir))
    print(f"Matrix from {source}: models={matrix['models']} defenses={len(matrix['defenses'])} "
          f"attacks={len(matrix['attack_strategies'])} cases={matrix['data_num']} -> {n_exp} experiments")

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    if not args.skip_run:
        if not (args.dry_run or args.no_preflight):
            for model in matrix["models"]:
                problem = check_ollama(model)
                if problem:
                    print(f"error: {problem}", file=sys.stderr)
                    return 2
        # run.py reads a matrix file, so write the (possibly filtered) matrix next to the logs.
        run_dir = REPO_ROOT / "log"
        run_dir.mkdir(exist_ok=True)
        matrix_file = run_dir / f"defense_sweep_{short_name(matrix['models'][0])}_matrix.json"
        matrix_file.write_text(json.dumps(matrix, indent=2) + "\n")
        print("Step 1/3: running the sweep (one request at a time)")
        code = subprocess.call(
            run_command(matrix_file, result_dir, args.max_retries, args.dry_run),
            cwd=REPO_ROOT, env=env,
        )
        if code != 0:
            print(f"run.py exited with {code}; rerun the same command to resume.", file=sys.stderr)
            return code
        if args.dry_run:
            return 0

    if args.skip_score:
        return 0

    finished = [d for d in result_dirs_for(matrix, result_dir) if (d / "experiment.json").is_file()]
    if not finished:
        print(f"error: no finished experiments under {result_dir}", file=sys.stderr)
        return 1
    if len(finished) < n_exp:
        print(f"warning: only {len(finished)}/{n_exp} experiments finished; scoring those", file=sys.stderr)

    print(f"Step 2/3: scoring {len(finished)} experiments into {out_dir}")
    code = subprocess.call(
        [sys.executable, str(REPO_ROOT / "scripts" / "score_responses.py"),
         *map(str, finished), "--out", str(out_dir)],
        cwd=REPO_ROOT, env=env,
    )
    if code != 0:
        return code

    print("Step 3/3: tables with 95% Wilson intervals")
    return subprocess.call(
        [sys.executable, str(REPO_ROOT / "scripts" / "final_tables.py"), str(out_dir)],
        cwd=REPO_ROOT, env=env,
    )


if __name__ == "__main__":
    sys.exit(main())
