import os
from typing import Any

from bfcl_eval.model_handler.api_inference.openai_completion import OpenAICompletionsHandler
from bfcl_eval.model_handler.utils import render_messages_for_log
from bfcl_eval.constants.enums import ModelStyle
from openai import OpenAI
from overrides import override
import time


class NanbeigeAPIHandler(OpenAICompletionsHandler):
    """
    This is the OpenAI-compatible API handler with streaming enabled.
    """

    # Nanbeige publishes no public API reference, so nothing here is claimed beyond
    # text. Flip a flag only against documentation or a live probe.
    can_handle_audio_input = False
    can_handle_image_input = False
    can_handle_image_tool_response = False

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_style = ModelStyle.OPENAI_COMPLETIONS
        self.client = OpenAI(
            base_url="https://nanbeige.zhipin.com/api/gpt/open/chat/openai/v1",
            api_key=os.getenv("NBG_API_KEY"),
        )

    #### FC methods ####
    @override
    def _query_FC(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        tools = inference_data["tools"]
        inference_data["inference_input_log"] = {"message": render_messages_for_log(message), "tools": tools}

        return self.generate_with_backoff(
            messages=inference_data["message"],
            model=self.model_name,
            tools=tools,
            timeout=72000,
        )

    @override
    def _parse_query_response_FC(self, api_response: Any) -> dict:
        tool_info = []
        reasoning_content = api_response.choices[0].message.reasoning_content
        answer_content = api_response.choices[0].message.content

        if api_response.choices[0].message.tool_calls:
            tool_calls = api_response.choices[0].message.tool_calls
            for tool_call in tool_calls:
                tool_info.append({})
                tool_info[-1]["id"] = tool_info[-1].get("id", "") + tool_call.id
                tool_info[-1]["name"] = (
                    tool_info[-1].get("name", "") + tool_call.function.name
                )
                tool_info[-1]["arguments"] = (
                    tool_info[-1].get("arguments", "") + tool_call.function.arguments
                )

        tool_call_ids = []
        for item in tool_info:
            tool_call_ids.append(item["id"])

        if len(tool_info) > 0:
            # Build tool_calls structure required by OpenAI-compatible API
            tool_calls_for_history = []
            for item in tool_info:
                tool_calls_for_history.append(
                    {
                        "id": item["id"],
                        "type": "function",
                        "function": {
                            "name": item["name"],
                            "arguments": item["arguments"],
                        },
                    }
                )

            model_response = [{item["name"]: item["arguments"]} for item in tool_info]
            model_response_message_for_chat_history = {
                "role": "assistant",
                "content": None,
                "tool_calls": tool_calls_for_history,
            }
            # Attach reasoning content so that it can be passed to the next turn
            if reasoning_content:
                model_response_message_for_chat_history["reasoning_content"] = (
                    reasoning_content
                )
        else:
            model_response = answer_content
            model_response_message_for_chat_history = {
                "role": "assistant",
                "content": answer_content,
            }
            # Attach reasoning content so that it can be passed to the next turn
            if reasoning_content:
                model_response_message_for_chat_history["reasoning_content"] = (
                    reasoning_content
                )

        response_data = {
            "model_responses": model_response,
            "model_responses_message_for_chat_history": model_response_message_for_chat_history,
            "reasoning_content": reasoning_content,
            "tool_call_ids": tool_call_ids,
            "input_token": api_response.usage.prompt_tokens,
            "output_token": api_response.usage.completion_tokens,
        }

        if not reasoning_content:
            del response_data["reasoning_content"]

        return response_data
