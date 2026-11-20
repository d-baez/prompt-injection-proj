"""Tests for how the Qwen wrapper asks the server to turn thinking off.

Ollama's OpenAI endpoint ignores ``chat_template_kwargs`` and ``think: false``;
only ``reasoning_effort: "none"`` disables qwen3 thinking there. The committed
Ollama config must use that style.

Run from the repo root:
    uv run python -m unittest discover -s tests -v
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OLLAMA_CONFIG = REPO_ROOT / "configs" / "model_configs" / "ollama_qwen3-8b_config.json"

try:
    from OpenPromptInjection.models.Qwen import Qwen
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False


def _config(style, thinking=False):
    config = json.loads(OLLAMA_CONFIG.read_text())
    config["params"]["thinking_parameter_style"] = style
    config["params"]["enable_thinking"] = thinking
    return config


class OllamaConfigTests(unittest.TestCase):
    def test_ollama_config_uses_reasoning_effort(self):
        params = json.loads(OLLAMA_CONFIG.read_text())["params"]
        self.assertEqual(params["thinking_parameter_style"], "reasoning_effort")
        self.assertFalse(params["enable_thinking"])


@unittest.skipUnless(HAVE_DEPS, "model dependencies not installed")
class ExtraBodyTests(unittest.TestCase):
    def test_reasoning_effort_none_when_thinking_off(self):
        self.assertEqual(Qwen(_config("reasoning_effort"))._extra_body(),
                         {"reasoning_effort": "none"})

    def test_reasoning_effort_omitted_when_thinking_on(self):
        self.assertEqual(Qwen(_config("reasoning_effort", thinking=True))._extra_body(), {})

    def test_chat_template_kwargs_unchanged(self):
        self.assertEqual(Qwen(_config("chat_template_kwargs"))._extra_body(),
                         {"chat_template_kwargs": {"enable_thinking": False}})

    def test_unknown_style_rejected(self):
        with self.assertRaisesRegex(ValueError, "reasoning_effort"):
            Qwen(_config("think_flag"))


if __name__ == "__main__":
    unittest.main()
