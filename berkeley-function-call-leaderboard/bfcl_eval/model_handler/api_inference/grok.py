import os
from typing import Any

from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from openai import OpenAI
from overrides import override


class GrokHandler(OpenAICompletionsHandler):
    # xAI documents image understanding but no audio input on the chat endpoint.
    can_handle_audio_input = False
    can_handle_image_input = True
    # Via the inherited placeholder-plus-user-message workaround: a Grok `tool`
    # message takes a plain string, like OpenAI's.
    can_handle_image_tool_response = True

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.client = OpenAI(
            base_url="https://api.x.ai/v1",
            api_key=os.getenv("GROK_API_KEY"),
        )

    @override
    def _parse_query_response_FC(self, api_response: Any) -> dict:
        response_data = super()._parse_query_response_FC(api_response)
        self._add_reasoning_content_if_available_FC(api_response, response_data)
        return response_data
