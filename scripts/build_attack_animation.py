"""Build graphify-out/attack_flow.html: an animated walk of one prompt-injection
attack through the code graph produced by graphify.

All prompt text is produced by the repo's own attacker/defense classes, and the
model responses/metrics come from evidence/scoring_sweep (qwen3:8b sweep). No
model calls are made.

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
SWEEP = ROOT / "evidence" / "scoring_sweep"
OUT = ROOT / "graphify-out" / "attack_flow.html"
TEMPLATE = Path(__file__).with_name("attack_flow_template.html")

MODEL_TAG = "ollama_qwen3-8b"
DATASET = "sst2"
DATA_NUM = 20
EXAMPLES = [0, 1, 2]
ATTACKS = ["naive", "escape", "ignore", "fake_comp", "combine"]
DEFENSES = ["no", "instructional", "delimiters", "xml", "sandwich", "random_seq",
            "known-answer", "response-based", "paraphrasing", "retokenization"]

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


def prompts():
    target = create_task(open_config(CONFIG_DIR / "task_configs" / f"{DATASET}_config.json"), DATA_NUM)
    injected = create_task(open_config(CONFIG_DIR / "task_configs" / f"{DATASET}_config.json"),
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


def results():
    res = {}
    for a in ATTACKS:
        for d in DEFENSES:
            folder = SWEEP / f"{MODEL_TAG}_{DATASET}_{DATASET}_{DATA_NUM}_{a}_{d}"
            if not folder.exists():
                continue
            summary = json.loads((folder / "score_summary.json").read_text())
            rows = [json.loads(l) for l in (folder / "scored_attack.jsonl").read_text().splitlines() if l.strip()]
            res[f"{a}|{d}"] = {
                "asv": summary["attacked"]["label_asv_repo_style"],
                "counts": summary["attacked"]["counts"],
                "clean_acc": summary["clean"]["label_accuracy"],
                "rows": {r["index"]: {k: r[k] for k in ("raw_response", "category", "label",
                                                        "true_label", "matches_injected_label", "blocked")}
                         for r in rows if r["index"] in EXAMPLES},
            }
    return res


def main():
    nodes, links = subgraph()
    data = {"nodes": nodes, "links": links, "prompts": prompts(), "results": results(),
            "model": "qwen3:8b (Ollama)", "attacks": ATTACKS, "defenses": DEFENSES}
    html = TEMPLATE.read_text().replace("/*__DATA__*/null", json.dumps(data).replace("</", "<\\/"))
    OUT.write_text(html)
    print(f"wrote {OUT} ({len(nodes)} nodes, {len(links)} edges, {len(data['results'])} runs)")


if __name__ == "__main__":
    main()
