"""Build graphify-out/attack_flow.html: an animated walk of one prompt-injection
attack through the code graph produced by graphify.

All prompt text is produced by the repo's own attacker/defense classes. The model
responses and metrics come from two sweeps, one per model:
  - qwen3:8b  (evidence/scoring_sweep): sentiment-style injected task, label-based ASV
  - mistral   (evidence/scoring_marker_mistral): INJECTED marker task, strict marker ASR
No model calls are made.

Run from the project root:
    PYTHONPATH=. ./.venv/bin/python scripts/build_attack_animation.py
"""
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

TARGET_DATASET = "sst2"
DATA_NUM = 20
EXAMPLES = [0, 1, 2]
ATTACKS = ["naive", "escape", "ignore", "fake_comp", "combine"]
DEFENSES = ["no", "instructional", "delimiters", "xml", "sandwich", "random_seq",
            "known-answer", "response-based", "paraphrasing", "retokenization"]

# One entry per model sweep shown in the flow.
RUNS = [
    {"id": "qwen3-8b", "label": "qwen3:8b · sentiment injection · Label-ASV",
     "model_tag": "ollama_qwen3-8b", "model": "qwen3:8b (Ollama)",
     "injected_dataset": "sst2", "sweep": "evidence/scoring_sweep", "metric": "Label-ASV"},
    {"id": "mistral", "label": "mistral · INJECTED marker · strict ASR",
     "model_tag": "ollama_mistral", "model": "mistral:latest (Ollama)",
     "injected_dataset": "injected_marker", "sweep": "evidence/scoring_marker_mistral",
     "metric": "Strict ASR"},
]

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


def prompts(injected_dataset):
    target = create_task(open_config(CONFIG_DIR / "task_configs" / f"{TARGET_DATASET}_config.json"), DATA_NUM)
    injected = create_task(open_config(CONFIG_DIR / "task_configs" / f"{injected_dataset}_config.json"),
                           DATA_NUM, for_injection=True)
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

    qwen3 (sentiment injection): ASV from the repo's label-based scorer; a row "matches"
    when it returns the injected label.
    mistral (marker injection): strict ASR; a row "matches" only when the response is
    exactly the marker (scoring.py category attack_succeeded). Responses that merely
    mention INJECTED are not counted as success.
    """
    res = {}
    for a in ATTACKS:
        for d in DEFENSES:
            folder = ROOT / run["sweep"] / f"{run['model_tag']}_{TARGET_DATASET}_{run['injected_dataset']}_{DATA_NUM}_{a}_{d}"
            if not folder.exists():
                continue
            summary = json.loads((folder / "score_summary.json").read_text())
            rows = [json.loads(l) for l in (folder / "scored_attack.jsonl").read_text().splitlines() if l.strip()]
            if run["id"] == "mistral":
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
    return res


def main():
    nodes, links = subgraph()
    runs = []
    for run in RUNS:
        runs.append({"id": run["id"], "label": run["label"], "model": run["model"],
                     "metric": run["metric"], "sweep": run["sweep"],
                     "prompts": prompts(run["injected_dataset"]), "results": results(run)})
    data = {"nodes": nodes, "links": links, "runs": runs,
            "attacks": ATTACKS, "defenses": DEFENSES}
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", json.dumps(data).replace("</", "<\\/"))
    OUT.write_text(html)
    counts = ", ".join(f"{r['id']}: {len(r['results'])} runs" for r in runs)
    print(f"wrote {OUT} ({len(nodes)} nodes, {len(links)} edges; {counts})")


if __name__ == "__main__":
    main()
