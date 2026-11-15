# Model choices for the defense evaluation

Hardware: 16 GB RAM, about 15 GB free disk. Run one 7–8B local model at a time.

## Picked models

| Role | Model | How | Status |
|---|---|---|---|
| Proposal model | GPT-4o-mini (OpenAI API) | Needs a config and API key | Not set up. Needs a key and an agreed dollar cap first. |
| Local, already downloaded | `qwen3:8b` | Ollama, `configs/model_configs/ollama_qwen3-8b_config.json` | Ready. Used for offline pipeline tests. |
| Local | `mistral:latest` (7B) | Ollama, `configs/model_configs/ollama_mistral_config.json` (provider `ollama`, generic wrapper in `OpenPromptInjection/models/Ollama.py`) | Downloaded (4.4 GB) and one test query passed. The old `mistral` config is for a GPU setup and is not used here. |
| Free hosted | Llama (via Groq free tier) | Free Groq account and key, OpenAI-compatible endpoint | Not set up. Needs a key and a check that the code accepts a base URL. |

## Not picked, and why

- `llama3.1:8b`, `phi4-mini`: a second local model would push disk use close to the limit. Add later if needed.
- OpenRouter `:free`, Hugging Face Inference: rate limits and changing terms. Use only if Groq is not enough.
- Google AI Studio (Gemini): needs new code. The old PaLM2 path won't work.
- PaLM2: on hold until the research is done.
- `gemma4-12b`, `qwen3.8-27b`: too large for this machine.

## Before any paid or hosted run

- Check each provider's terms for data use. SST-2 is public, so the data is fine, but the proposal says to follow API terms.
- Agree the dollar cap with the team.
- Freeze the model snapshot and decoding settings before the final run.
