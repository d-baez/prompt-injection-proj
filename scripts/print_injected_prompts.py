"""Print the exact prompts each attack would send to the model. No API calls.

Run from the project root:
    PYTHONPATH=. ./.venv/bin/python <path to this file>
"""
from OpenPromptInjection.utils import CONFIG_DIR, open_config
from OpenPromptInjection.tasks import create_task
from OpenPromptInjection.attackers import create_attacker

TARGET_CONFIG = CONFIG_DIR / "task_configs" / "sst2_config.json"    # sentiment analysis (trusted task)
INJECTED_CONFIG = CONFIG_DIR / "task_configs" / "hsol_config.json"  # hate detection (injected task)
DATA_NUM = 100          # matches the cached data folders in data/
EXAMPLE_IDXS = [0, 1, 2]
ATTACKS = ["ignore", "fake_comp"]
TARGET_TASK_NAME = "sentiment_analysis"  # used by fake_comp to pick its fake answer

target = create_task(open_config(TARGET_CONFIG), DATA_NUM, for_injection=False)
injected = create_task(open_config(INJECTED_CONFIG), DATA_NUM, for_injection=True)

print("TRUSTED TASK INSTRUCTION:")
print(f"  {target.get_instruction()}")
print("INJECTED TASK INSTRUCTION:")
print(f"  {injected.get_instruction()}")

for idx in EXAMPLE_IDXS:
    clean_data, clean_label = target[idx]
    print("\n" + "=" * 100)
    print(f"EXAMPLE idx={idx}  clean label={clean_label}")
    print("-" * 100)
    print("CLEAN REVIEW (no attack):")
    print(clean_data)

    for strategy in ATTACKS:
        attacker = create_attacker(strategy, injected)
        print("-" * 100)
        print(f"ATTACK: {strategy}")
        print("get_injected_prompt() -- the attack text on its own:")
        print(attacker.get_injected_prompt(clean_data, idx, TARGET_TASK_NAME))
        print()
        print("inject() -- the full untrusted data the model receives:")
        print(attacker.inject(clean_data, idx, TARGET_TASK_NAME))
