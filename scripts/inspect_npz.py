"""Print a readable summary of .npz files (keys, shapes, dtypes, and sample values).

Examples (run from the repo root):
    uv run python scripts/inspect_npz.py result/ollama_qwen3-8b_sst2_sst2_20_ignore_no/attack_responses.npz
    uv run python scripts/inspect_npz.py result/ollama_qwen3-8b_sst2_sst2_20_ignore_no --rows 5
    uv run python scripts/inspect_npz.py data/sentiment_analysis_sst2_validation_100 --allow-pickle

Pickle loading is off by default because .npz files can hold pickled objects
that run code when loaded. Use --allow-pickle only for files you trust.
"""
import argparse
import sys
from pathlib import Path

import numpy as np


def iter_npz_files(paths):
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            yield from sorted(path.rglob("*.npz"))
        elif path.is_file():
            yield path
        else:
            print(f"warning: {path} does not exist", file=sys.stderr)


def describe_array(name, array, rows, width):
    print(f"  [{name}] shape={array.shape} dtype={array.dtype}")
    flat = array.reshape(-1) if array.ndim else array.reshape(1)
    for value in flat[:rows]:
        text = repr(value.item() if isinstance(value, np.generic) else value)
        if len(text) > width:
            text = text[: width - 3] + "..."
        print(f"      {text}")
    if flat.size > rows:
        print(f"      ... ({flat.size - rows} more)")


def inspect_file(path, rows, width, allow_pickle):
    print(f"== {path}")
    try:
        with np.load(path, allow_pickle=allow_pickle) as data:
            if not data.files:
                print("  (no arrays)")
            for name in data.files:
                try:
                    describe_array(name, data[name], rows, width)
                except ValueError as exc:
                    print(f"  [{name}] could not read: {exc}")
    except ValueError as exc:
        print(f"  could not open: {exc}")
        if not allow_pickle:
            print("  hint: this file may contain pickled objects; retry with --allow-pickle if you trust it")
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help=".npz files or directories (searched recursively)")
    parser.add_argument("--rows", type=int, default=3, help="number of values to show per array (default: 3)")
    parser.add_argument("--width", type=int, default=160, help="max characters per value (default: 160)")
    parser.add_argument("--allow-pickle", action="store_true", help="allow loading pickled object arrays (trusted files only)")
    args = parser.parse_args()

    files = list(iter_npz_files(args.paths))
    if not files:
        print("no .npz files found", file=sys.stderr)
        return 1
    for path in files:
        inspect_file(path, args.rows, args.width, args.allow_pickle)
    return 0


if __name__ == "__main__":
    sys.exit(main())
