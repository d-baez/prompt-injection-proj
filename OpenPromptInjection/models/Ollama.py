"""Generic chat model served by a local Ollama server through its OpenAI-compatible API.

Sends only the standard chat fields, so it works for any model Ollama serves
(for example ``mistral:latest``) without model-specific options.
"""

import logging

from openai import OpenAI

from .Model import Model


LOGGER = logging.getLogger(__name__)


class Ollama(Model):
    def __init__(self, config):
        super().__init__(config)
        key_info = config.get("api_key_info", {})
        api_keys = key_info.get("api_keys", [])
        api_pos = int(key_info.get("api_key_use", 0))
        if not 0 <= api_pos < len(api_keys):
            raise ValueError(
                f"api_key_use {api_pos} is invalid for {len(api_keys)} configured keys"
            )

        self.base_url = key_info.get("base_url")
        if not self.base_url:
            raise ValueError("Ollama requires api_key_info.base_url")
        # Ollama ignores the key, but the OpenAI client requires a non-empty one.
        api_key = str(api_keys[api_pos]) or "ollama"
        self.client = OpenAI(api_key=api_key, base_url=self.base_url)

        self.max_output_tokens = int(config["params"]["max_output_tokens"])

    def print_model_info(self):
        LOGGER.info(
            "Model provider=%s, name=%s, sampling=%s, endpoint=%s",
            self.provider,
            self.name,
            self.do_sample,
            self.base_url,
        )

    def query(self, msg):
        request = {
            "model": self.name,
            "messages": [{"role": "user", "content": msg}],
            "max_tokens": self.max_output_tokens,
            "seed": self.seed,
            "temperature": self.temperature if self.do_sample else 0.0,
        }
        completion = self.client.chat.completions.create(**request)
        response = completion.choices[0].message.content
        if response is None:
            raise ValueError("Ollama endpoint returned an empty response")
        return response
