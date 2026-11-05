"""Print the exact prompts each defense sends, for each attack. No model is called.

Owner: Michael Cardenas.

This is the defense sanity check: it runs the repo's real ``Application`` and
real ``ignore`` / ``fake_comp`` attackers, but swaps the model for a recorder
that stores the prompt and returns an empty string. The output shows, for one
clean SST-2-style sentence, what the model would receive under
``no``, ``delimiters`` and ``instructional``.

Run from the repo root:
    PYTHONPATH=. python3 scripts/show_defense_prompts.py
    PYTHONPATH=. python3 scripts/show_defense_prompts.py --out evidence/defense_prompt_trace.txt
"""
import argparse
from pathlib import Path

import OpenPromptInjection as PI
from OpenPromptInjection.utils.paths import SYSTEM_PROMPT_DIR

DEFENSES = ("no", "delimiters", "instructional")
ATTACKS = ("ignore", "fake_comp")

CLEAN_TEXT = "a gorgeous , witty , seductive movie ."
INJECTED_TEXT = "the plot is a dull , lifeless mess ."


class StandInTask:
    """The minimum of the task interface that Application and attackers use."""

    def __init__(self, instruction, data, for_injection):
        self.task = "sentiment_analysis"
        self.dataset = "sst2"
        self._instruction = instruction
        self._data = data
        self._for_injection = for_injection

    def for_injection(self):
        return self._for_injection

    def get_instruction(self):
        return self._instruction

    def __getitem__(self, idx):
        return self._data, 0

    def __len__(self):
        return 1


class RecordingModel:
    name = "recording-stub"

    def __init__(self):
        self.prompts = []

    def query(self, prompt):
        self.prompts.append(prompt)
        return ""


def _instruction(name):
    return (SYSTEM_PROMPT_DIR / f"{name}.txt").read_text().strip()


def build_trace():
    target = StandInTask(_instruction("sentiment_analysis"), CLEAN_TEXT, False)
    injected = StandInTask(_instruction("sentiment_analysis_inject"), INJECTED_TEXT, True)
    sections = []
    for defense in DEFENSES:
        model = RecordingModel()
        app = PI.create_app(target, model, defense=defense)
        app.query(CLEAN_TEXT, verbose=0)
        sections.append((f"defense={defense} | clean", model.prompts[-1]))
        for attack in ATTACKS:
            attacker = PI.create_attacker(attack, injected)
            attacked = attacker.inject(CLEAN_TEXT, 0, target_task=target.task)
            app.query(attacked, verbose=0)
            sections.append((f"defense={defense} | attack={attack}", model.prompts[-1]))
    return sections


def render(sections):
    bar = "=" * 72
    return "\n".join(f"{bar}\n{title}\n{bar}\n{prompt}\n" for title, prompt in sections)


def main():
    parser = argparse.ArgumentParser(description="Show defended prompts without calling a model.")
    parser.add_argument("--out", type=Path, help="also write the trace to this file")
    args = parser.parse_args()
    text = render(build_trace())
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)


if __name__ == "__main__":
    main()
