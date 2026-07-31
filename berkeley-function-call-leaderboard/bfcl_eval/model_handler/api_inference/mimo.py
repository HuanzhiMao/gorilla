import os

from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from openai import OpenAI


class MiMoHandler(OpenAICompletionsHandler):
    """Xiaomi's MiMo platform, which serves an OpenAI-compatible chat completions API."""

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.client = OpenAI(
            base_url="https://api.xiaomimimo.com/v1",
            api_key=os.getenv("MIMO_API_KEY"),
        )
