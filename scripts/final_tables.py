"""Tables with 95% Wilson intervals for a scored final folder (no model calls).

Reads <folder>/<experiment>/score_summary.json and scored_*.jsonl written by
scripts/score_responses.py and writes <folder>/tables.md and tables.json:
  - per-defense strict ASR pooled over the 5 attacks (n = 500), with CI
  - defense x attack strict ASR grid
  - clean accuracy per defense, with CI
  - change vs no defense: ASR reduction (pp and relative) and clean-accuracy change,
    with 95% Newcombe intervals, pooled and per attack
  - artifact counts: split marker (INJECTED once whitespace is removed), label collapse on
    attacked prompts, blank (blocked) clean answers

    uv run python scripts/final_tables.py evidence/final100_qwen3-8b
"""
import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ATTACKS = ["naive", "escape", "ignore", "fake_comp", "combine"]


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fmt(k, n):
    lo, hi = wilson(k, n)
    return f"{100 * k / n:.1f}% [{100 * lo:.1f}, {100 * hi:.1f}]"


def newcombe(k1, n1, k2, n2):
    """95% interval for p1 - p2 (Newcombe hybrid score method, from two Wilson intervals).

    Treats the two proportions as independent. The defended and undefended runs use the
    same cases, so this is slightly conservative for our paired design.
    """
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    d = p1 - p2
    return (d - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2),
            d + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2))


def vs_no_defense(pooled, baseline="no"):
    """Per-defense change relative to the no-defense run (Michael's metrics layer).

    asr_reduction_pp:   ASR(no) - ASR(defense), percentage points (positive = defense helped)
    asr_reduction_rel:  asr_reduction_pp / ASR(no), share of baseline attacks removed
    clean_change_pp:    accuracy(defense) - accuracy(no), percentage points (negative = cost)
    Each _pp value comes with a 95% Newcombe interval.
    """
    if baseline not in pooled:
        return {}
    b = pooled[baseline]
    b_asr, b_acc = b["exact"] / b["n"], b["clean_correct"] / b["clean_n"]
    result = {}
    for d, p in pooled.items():
        if d == baseline:
            continue
        asr, acc = p["exact"] / p["n"], p["clean_correct"] / p["clean_n"]
        red_lo, red_hi = newcombe(b["exact"], b["n"], p["exact"], p["n"])
        acc_lo, acc_hi = newcombe(p["clean_correct"], p["clean_n"], b["clean_correct"], b["clean_n"])
        result[d] = {
            "asr": asr,
            "asr_reduction_pp": 100 * (b_asr - asr),
            "asr_reduction_pp_ci": [100 * red_lo, 100 * red_hi],
            "asr_reduction_rel": (b_asr - asr) / b_asr if b_asr else None,
            "clean_accuracy": acc,
            "clean_change_pp": 100 * (acc - b_acc),
            "clean_change_pp_ci": [100 * acc_lo, 100 * acc_hi],
        }
    return result


def _pp(value, ci):
    return f"{value:+.1f} [{ci[0]:+.1f}, {ci[1]:+.1f}]"


def _split_marker(row):
    text = row["raw_response"] or ""
    return "INJECTED" not in text and "INJECTED" in re.sub(r"\s+", "", text)


def rows(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    args = parser.parse_args(argv)

    per = {}
    for summary_path in sorted(args.folder.glob("*/score_summary.json")):
        s = json.loads(summary_path.read_text())
        d = summary_path.parent
        attack_rows, clean_rows = rows(d / "scored_attack.jsonl"), rows(d / "scored_clean.jsonl")
        per[(s["defense"], s["attack"])] = {
            "n": s["attacked"]["n"],
            "exact": s["attacked"]["counts"]["attack_succeeded"],
            "present": sum(r["marker_present"] for r in attack_rows),
            # Split marker: INJECTED only once whitespace is removed (retokenization
            # echoes it as "I N J E C T E D" or "I NJE CTED").
            "spaced": sum(_split_marker(r) for r in attack_rows),
            "blocked": s["attacked"]["counts"]["blocked"],
            "attacked_labels": Counter(str(r["label"]) for r in attack_rows),
            "clean_n": s["clean"]["n"],
            "clean_correct": s["clean"]["counts"]["correct_label"],
            "clean_invalid": s["clean"]["counts"]["invalid"],
            "clean_blocked": s["clean"]["counts"]["blocked"],
        }
    if not per:
        print("no scored experiments", file=sys.stderr)
        return 1

    defenses = sorted({d for d, _ in per})
    pooled = {}
    for d in defenses:
        cells = [per[(d, a)] for a in ATTACKS if (d, a) in per]
        agg = defaultdict(int)
        labels = Counter()
        for c in cells:
            for k in ("n", "exact", "present", "spaced", "blocked"):
                agg[k] += c[k]
            labels += c["attacked_labels"]
        # Clean prompts don't depend on the attack: every cell re-queries the
        # same clean prompts, so take one cell's clean counts, not the sum.
        first = cells[0]
        agg.update({k: first[k] for k in ("clean_n", "clean_correct", "clean_invalid", "clean_blocked")})
        agg["attacked_labels"] = dict(labels)
        agg["attacks"] = len(cells)
        pooled[d] = dict(agg)

    order = sorted(defenses, key=lambda d: -pooled[d]["exact"] / pooled[d]["n"])
    out = ["# Final tables (95% Wilson intervals)", "",
           f"Source: `{args.folder}`, generated by `scripts/final_tables.py`.", "",
           "## Strict ASR by defense, pooled over attacks",
           "", "| Defense | Attacks | n | Exact `INJECTED` | `INJECTED` present | Split marker (`I N J E C T E D`, `I NJE CTED`) | Blocked |",
           "|---|---|---|---|---|---|---|"]
    for d in order:
        p = pooled[d]
        out.append(f"| {d} | {p['attacks']} | {p['n']} | {fmt(p['exact'], p['n'])} | "
                   f"{fmt(p['present'], p['n'])} | {p['spaced']} | {p['blocked']} |")
    out += ["", "## Strict ASR, defense x attack (n = 100 per cell)", "",
            "| Defense | " + " | ".join(ATTACKS) + " |", "|---|" + "---|" * len(ATTACKS)]
    for d in order:
        cells = [f"{per[(d, a)]['exact']}" if (d, a) in per else "–" for a in ATTACKS]
        out.append(f"| {d} | " + " | ".join(cells) + " |")
    out += ["", "## Clean accuracy by defense (strict; invalid counts as wrong)", "",
            "| Defense | n | Accuracy | Invalid | Blocked |", "|---|---|---|---|---|"]
    for d in order:
        p = pooled[d]
        out.append(f"| {d} | {p['clean_n']} | {fmt(p['clean_correct'], p['clean_n'])} | "
                   f"{p['clean_invalid']} | {p['clean_blocked']} |")
    deltas = vs_no_defense(pooled)
    if deltas:
        b = pooled["no"]
        out += ["", "## Change relative to no defense (ASR reduction and clean-accuracy cost)", "",
                f"Baseline (no defense): strict ASR {100 * b['exact'] / b['n']:.1f}%, "
                f"clean accuracy {100 * b['clean_correct'] / b['clean_n']:.1f}%. "
                "Differences in percentage points with 95% Newcombe intervals. "
                "A positive ASR reduction means fewer successful attacks; a negative clean change "
                "means the defense costs accuracy. Read with the artifact notes in FINDINGS.md: "
                "a reduction from paraphrasing, response-based or retokenization isn't a clean defense result.", "",
                "| Defense | ASR reduction (pp) | Relative ASR reduction | Clean accuracy change (pp) |",
                "|---|---|---|---|"]
        for d in [x for x in order if x in deltas]:
            r = deltas[d]
            rel = "–" if r["asr_reduction_rel"] is None else f"{100 * r['asr_reduction_rel']:.1f}%"
            out.append(f"| {d} | {_pp(r['asr_reduction_pp'], r['asr_reduction_pp_ci'])} | {rel} | "
                       f"{_pp(r['clean_change_pp'], r['clean_change_pp_ci'])} |")
        out += ["", "## ASR reduction by attack (percentage points vs no defense, n = 100 per cell)", "",
                "| Defense | " + " | ".join(ATTACKS) + " |", "|---|" + "---|" * len(ATTACKS)]
        for d in [x for x in order if x in deltas]:
            cells = []
            for a in ATTACKS:
                if (d, a) in per and ("no", a) in per:
                    base, cell = per[("no", a)], per[(d, a)]
                    cells.append(f"{100 * (base['exact'] / base['n'] - cell['exact'] / cell['n']):+.0f}")
                else:
                    cells.append("–")
            out.append(f"| {d} | " + " | ".join(cells) + " |")
    out += ["", "## Labels returned on attacked prompts (pooled)", "",
            "`label` is the strict sentiment label (0 negative, 1 positive), `None` when the answer isn't a single label.", "",
            "| Defense | Labels |", "|---|---|"]
    for d in order:
        labels = ", ".join(f"{k}: {v}" for k, v in sorted(pooled[d]["attacked_labels"].items()))
        out.append(f"| {d} | {labels} |")
    (args.folder / "tables.md").write_text("\n".join(out) + "\n")
    (args.folder / "tables.json").write_text(json.dumps(
        {"pooled": pooled,
         "vs_no_defense": deltas,
         "cells": {f"{d}|{a}": {k: v for k, v in c.items() if k != "attacked_labels"}
                   for (d, a), c in per.items()}}, indent=2) + "\n")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
