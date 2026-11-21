import logging

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from .Model import Model


LOGGER = logging.getLogger(__name__)

# Disable every adjustable text safety filter so the model's own behavior is what
# gets measured, matching the BLOCK_NONE settings the original PaLM code used.
_SAFETY_CATEGORIES = (
    types.HarmCategory.HARM_CATEGORY_HARASSMENT,
    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    types.HarmCategory.HARM_CATEGORY_CIVIC_INTEGRITY,
)
_SAFETY_SETTINGS = [
    types.SafetySetting(category=category, threshold=types.HarmBlockThreshold.BLOCK_NONE)
    for category in _SAFETY_CATEGORIES
]


class PaLM2(Model):
    """Google generative model backed by the `google-genai` SDK.

    The PaLM API (text-bison, chat-bison) has been retired, so this class now
    calls Gemini models. The class name and the 'palm2' provider key are kept so
    existing configs and run matrices keep working; 'gemini' is also accepted.
    """

    def __init__(self, config):
        super().__init__(config)
        api_keys = config["api_key_info"]["api_keys"]
        api_pos = int(config["api_key_info"]["api_key_use"])
        assert (0 <= api_pos < len(api_keys)), "Please enter a valid API key to use"
        self.api_key = api_keys[api_pos]
        self.max_output_tokens = int(config["params"]["max_output_tokens"])
        self.set_API_key()

    def set_API_key(self):
        self.client = genai.Client(api_key=self.api_key)

    def _generation_config(self):
        return types.GenerateContentConfig(
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            seed=self.seed,
            candidate_count=1,
            safety_settings=_SAFETY_SETTINGS,
        )

    def query(self, msg):
        try:
            completion = self.client.models.generate_content(
                model=self.name,
                contents=msg,
                config=self._generation_config(),
            )
            response = completion.text or ""
        except genai_errors.ClientError as exc:
            if exc.code == 429:
                LOGGER.error("Gemini rate limit or quota exhausted: %s", exc)
            else:
                LOGGER.error("Gemini rejected the request: %s", exc)
            response = ""
        except Exception:
            LOGGER.exception("Unexpected Gemini query failure")
            response = ""

        return response
