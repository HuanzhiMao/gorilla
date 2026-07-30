import os

from bfcl_eval.constants.enums import ModelStyle
from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from openai import OpenAI
from overrides import override


class MetaHandler(OpenAICompletionsHandler):
    """
    Handler for Meta's Muse Spark models, served through the Meta Model API.

    The Meta Model API speaks the OpenAI Chat Completions protocol, so we only need
    to point the client at Meta's base URL and drop the OpenAI-only request fields.
    https://ai.developer.meta.com/docs/getting-started/overview/
    """

    can_handle_audio_input = False
    can_handle_image_input = True
    can_handle_image_tool_response = True

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_style = ModelStyle.OPENAI_COMPLETIONS
        # Meta's docs name the key `MODEL_API_KEY`, which is too generic to sit next
        # to the other vendor keys in `.env`, so we prefer `META_API_KEY` and fall
        # back to the documented name.
        self.client = OpenAI(
            base_url="https://api.meta.ai/v1",
            api_key=os.getenv("META_API_KEY"),
        )

    @override
    def _query_FC(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        tools = inference_data["tools"]
        inference_data["inference_input_log"] = {"message": repr(message), "tools": tools}

        # `store` is an OpenAI-only field, and we omit `temperature` because Muse Spark
        # is a reasoning model (depth is controlled by `reasoning_effort` instead; we
        # run it at Meta's default effort).
        kwargs = {
            "messages": message,
            "model": self.model_name,
        }

        if len(tools) > 0:
            kwargs["tools"] = tools

        return self.generate_with_backoff(**kwargs)
