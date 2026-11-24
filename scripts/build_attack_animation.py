"""Build graphify-out/attack_flow.html: an animated walk of one prompt-injection
attack through the code graph produced by graphify.

All prompt text is produced by the repo's own attacker/defense classes. The model
responses and metrics come from the scored sweeps listed in RUNS (one entry per sweep;
each sets its own target dataset and sample count). No model calls are made.

To add a sweep, append a RUNS entry. Its result folders must be named the way run.py
names them: {model_tag}_{target_dataset}_{injected_dataset}_{data_num}_{attack}_{defense}.

Run from the project root:
    PYTHONPATH=. ./.venv/bin/python scripts/build_attack_animation.py

Public copy for db444.xyz/attack-demo (vis-network served from the same origin):
    PYTHONPATH=. ./.venv/bin/python scripts/build_attack_animation.py \
        --out ../db444-hub/public/attack-demo/index.html --vis-src /attack-demo/vis-network.min.js
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from OpenPromptInjection.apps import defenses as D
from OpenPromptInjection.attackers import create_attacker
from OpenPromptInjection.tasks import create_task
from OpenPromptInjection.utils import CONFIG_DIR, open_config

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT / "graphify-out" / "graph.json"
OUT = ROOT / "graphify-out" / "attack_flow.html"
TEMPLATE = Path(__file__).with_name("attack_flow_template.html")
VIS_CDN = "https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"

EXAMPLES = [0, 1, 2]  # sample indices shown in the walkthrough (within each run's split)
ATTACKS = ["naive", "escape", "ignore", "fake_comp", "combine"]
DEFENSES = ["no", "instructional", "delimiters", "xml", "sandwich", "random_seq",
            "known-answer", "response-based", "paraphrasing", "retokenization"]

# One entry per sweep shown in the flow.
#   model_tag / target_dataset / injected_dataset / data_num: the run.py matrix values
#   scoring: "label" (qwen-style label ASV) or "marker" (strict INJECTED-marker ASR)
RUNS = [
    # Final 100-case sweeps on the disjoint sst2final split (strict INJECTED-marker ASR).
    {"id": "llama3.1-8b-final", "label": "llama3.1:8b · final · INJECTED marker · strict ASR",
     "model_tag": "ollama_llama3.1-8b", "model": "llama3.1:8b (Ollama)",
     "target_dataset": "sst2final", "injected_dataset": "injected_marker", "data_num": 100,
     "sweep": "evidence/final100_llama3.1-8b", "scoring": "marker"},
    {"id": "mistral-final", "label": "mistral · final · INJECTED marker · strict ASR",
     "model_tag": "ollama_mistral_final", "model": "mistral:latest (Ollama)",
     "target_dataset": "sst2final", "injected_dataset": "injected_marker", "data_num": 100,
     "sweep": "evidence/final100_mistral", "scoring": "marker"},
    {"id": "qwen3-8b-final", "label": "qwen3:8b · final · INJECTED marker · strict ASR",
     "model_tag": "ollama_qwen3-8b", "model": "qwen3:8b (Ollama)",
     "target_dataset": "sst2final", "injected_dataset": "injected_marker", "data_num": 100,
     "sweep": "evidence/final100_qwen3-8b", "scoring": "marker"},
    # Earlier 20-case pilot sweeps.
    {"id": "qwen3-8b", "label": "qwen3:8b · pilot · sentiment injection · Label-ASV",
     "model_tag": "ollama_qwen3-8b", "model": "qwen3:8b (Ollama)",
     "target_dataset": "sst2", "injected_dataset": "sst2", "data_num": 20,
     "sweep": "evidence/scoring_sweep", "scoring": "label"},
    {"id": "mistral", "label": "mistral · pilot · INJECTED marker · strict ASR",
     "model_tag": "ollama_mistral", "model": "mistral:latest (Ollama)",
     "target_dataset": "sst2", "injected_dataset": "injected_marker", "data_num": 20,
     "sweep": "evidence/scoring_marker_mistral", "scoring": "marker"},
]
METRIC = {"label": "Label-ASV", "marker": "Strict ASR"}

KEEP_PREFIXES = (
    "main.py",
    "OpenPromptInjection/attackers/",
    "OpenPromptInjection/apps/Application.py",
    "OpenPromptInjection/apps/defenses.py",
    "OpenPromptInjection/apps/__init__.py",
    "OpenPromptInjection/models/Model.py",
    "OpenPromptInjection/models/Ollama.py",
    "OpenPromptInjection/models/__init__.py",
    "OpenPromptInjection/tasks/Task.py",
    "OpenPromptInjection/tasks/TargetTask.py",
    "OpenPromptInjection/tasks/InjectedTask.py",
    "OpenPromptInjection/tasks/__init__.py",
    "OpenPromptInjection/evaluator/",
)


def subgraph():
    g = json.loads(GRAPH.read_text())
    nodes = [n for n in g["nodes"]
             if n.get("file_type") == "code"
             and str(n.get("source_file", "")).startswith(KEEP_PREFIXES)]
    ids = {n["id"] for n in nodes}
    links = [{"from": e["source"], "to": e["target"], "rel": e.get("relation", "")}
             for e in g["links"] if e["source"] in ids and e["target"] in ids]
    return [{"id": n["id"], "label": n["label"], "group": n.get("community_name", ""),
             "file": n.get("source_file", ""), "loc": n.get("source_location", "")}
            for n in nodes], links


def prompts(run):
    n = run["data_num"]
    target = create_task(open_config(CONFIG_DIR / "task_configs" / f"{run['target_dataset']}_config.json"), n)
    injected = create_task(open_config(CONFIG_DIR / "task_configs" / f"{run['injected_dataset']}_config.json"),
                           n, for_injection=True)
    app = SimpleNamespace(task=target)
    prompt_defenses = {
        "no": D.Defense, "instructional": D.InstructionalDefense,
        "delimiters": D.DelimiterDefense, "xml": D.XmlDefense,
        "sandwich": D.SandwichDefense, "random_seq": D.RandomSequenceDefense,
    }
    out = {"target_instruction": target.get_instruction(),
           "injected_instruction": injected.get_instruction(),
           "target_task": target.task, "examples": []}
    for idx in EXAMPLES:
        clean, label = target[idx]
        ex = {"idx": idx, "clean": clean, "label": int(label),
              "injected_data": injected[idx][0], "attacks": {}}
        for a in ATTACKS:
            attacker = create_attacker(a, injected)
            payload = attacker.inject(clean, idx, target_task=target.task)
            per_def = {}
            for d in DEFENSES:
                cls = prompt_defenses.get(d, D.Defense)
                strat = cls(app)
                instr = strat.prepare_instruction(target.get_instruction())
                per_def[d] = strat.build_prompt(instr, payload)
            ex["attacks"][a] = {"payload": payload,
                                "injected_part": attacker.get_injected_prompt(clean, idx, target.task),
                                "prompts": per_def}
        out["examples"].append(ex)
    return out


def results(run):
    """Per attack x defense: the run's headline metric plus the scored example rows.

    scoring "label" (sentiment injection): ASV from the repo's label-based scorer; a row
    "matches" when it returns the injected label.
    scoring "marker" (marker injection): strict ASR; a row "matches" only when the response
    is exactly the marker (scoring.py category attack_succeeded). Responses that merely
    mention INJECTED are not counted as success.
    """
    if run["scoring"] not in METRIC:
        raise ValueError(f"{run['id']}: unknown scoring {run['scoring']!r}")
    res, missing = {}, []
    for a in ATTACKS:
        for d in DEFENSES:
            folder = ROOT / run["sweep"] / (f"{run['model_tag']}_{run['target_dataset']}_{run['injected_dataset']}"
                                            f"_{run['data_num']}_{a}_{d}")
            if not folder.exists():
                missing.append(folder.name)
                continue
            summary = json.loads((folder / "score_summary.json").read_text())
            rows = [json.loads(l) for l in (folder / "scored_attack.jsonl").read_text().splitlines() if l.strip()]
            if run["scoring"] == "marker":
                asr = summary["attacked"]["asr_strict"]
                matches = lambda r: r["category"] == "attack_succeeded"
            else:
                asr = summary["attacked"]["label_asv_repo_style"]
                matches = lambda r: bool(r.get("matches_injected_label"))
            res[f"{a}|{d}"] = {
                "asr": asr,
                "counts": summary["attacked"]["counts"],
                "clean_acc": summary["clean"]["label_accuracy"],
                "rows": {r["index"]: {"raw_response": r["raw_response"], "category": r["category"],
                                      "label": r["label"], "true_label": r["true_label"],
                                      "matches_injected_label": matches(r), "blocked": r["blocked"]}
                         for r in rows if r["index"] in EXAMPLES},
            }
    if missing:
        print(f"warning: {run['id']}: {len(missing)} of {len(ATTACKS) * len(DEFENSES)} result folders missing "
              f"(shown as '–'), e.g. {run['sweep']}/{missing[0]}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=OUT, help="output HTML path")
    ap.add_argument("--vis-src", default=VIS_CDN,
                    help="vis-network script URL; a local copy must match the pinned SRI hash")
    args = ap.parse_args()
    nodes, links = subgraph()
    runs = []
    for run in RUNS:
        runs.append({"id": run["id"], "label": run["label"], "model": run["model"],
                     "metric": METRIC[run["scoring"]], "sweep": run["sweep"], "n": run["data_num"],
                     "target_dataset": run["target_dataset"],
                     "prompts": prompts(run), "results": results(run)})
    data = {"nodes": nodes, "links": links, "runs": runs,
            "attacks": ATTACKS, "defenses": DEFENSES}
    template = TEMPLATE.read_text()
    assert template.count(VIS_CDN) == 1
    html = (template.replace(VIS_CDN, args.vis_src)
            .replace("/*__DATA__*/null", json.dumps(data).replace("</", "<\\/")))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html)
    counts = ", ".join(f"{r['id']}: {len(r['results'])} runs" for r in runs)
    print(f"wrote {args.out} ({len(nodes)} nodes, {len(links)} edges; {counts})")


if __name__ == "__main__":
    main()
