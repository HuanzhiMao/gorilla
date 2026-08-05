import os
from typing import Any

from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from bfcl_eval.model_handler.utils import render_messages_for_log
from openai import OpenAI
from overrides import override


class KimiHandler(OpenAICompletionsHandler):
    # Moonshot documents no audio input for K3.
    can_handle_audio_input = False
    # K3 reads images from a base64 data URI (public http URLs are rejected), which is
    # exactly the shape the base handler emits.
    can_handle_image_input = True
    # Via the inherited workaround. This handler used to override
    # `_add_execution_results_FC` to put an `image_url` part directly inside a
    # `role="tool"` message. Nothing in Moonshot's docs sanctions that, and the
    # OpenAI-compatible schema it implements narrows tool-message content to text --
    # so the override is gone and the documented placeholder-plus-user-message path
    # is used instead. Restore it only with evidence from a live probe.
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
            base_url="https://api.moonshot.ai/v1",
            # If API Key is from US platform, use the above URL
            # If API Key is from China platform, use the below URL
            # base_url="https://api.moonshot.cn/v1",
            api_key=os.getenv("KIMI_API_KEY")
        )

    @override
    def _query_FC(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        tools = inference_data["tools"]
        inference_data["inference_input_log"] = {"message": render_messages_for_log(message), "tools": tools}

        kwargs = {
            "messages": message,
            "model": self.model_name,
            "temperature": 1,
            "store": False,
        }

        if len(tools) > 0:
            kwargs["tools"] = tools

        return self.generate_with_backoff(**kwargs)

    @override
    def _parse_query_response_FC(self, api_response: Any) -> dict:
        response_data = super()._parse_query_response_FC(api_response)

        # Kimi K2.5 thinking mode requires reasoning_content to be echoed back
        # in subsequent assistant tool-call messages; the base handler strips it.
        message = api_response.choices[0].message
        reasoning_content = getattr(message, "reasoning_content", None)
        if reasoning_content:
            response_data["model_responses_message_for_chat_history"][
                "reasoning_content"
            ] = reasoning_content
            response_data["reasoning_content"] = reasoning_content

        return response_data

