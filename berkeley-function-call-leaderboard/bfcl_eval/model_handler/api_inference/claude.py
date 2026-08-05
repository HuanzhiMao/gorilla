import json
import os
import time
from typing import Any

from anthropic import Anthropic, RateLimitError
from anthropic.types import TextBlock, ToolUseBlock
from bfcl_eval.constants.enums import ModelStyle, ResultType
from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.model_handler.utils import (
    combine_consecutive_user_prompts,
    convert_to_function_call,
    convert_to_tool,
    extract_system_prompt,
    render_messages_for_log,
    retry_with_backoff,
)
from bfcl_eval.utils import contain_multi_step_interaction
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.message import Message


class ClaudeHandler(BaseHandler):
    # The Messages API has no audio content block at all -- the request-side block
    # union is text / image / document / search_result / thinking / tool_* -- and the
    # installed anthropic SDK ships no audio type either. Documents are PDF and plain
    # text only, so there is no back door for an mp3.
    can_handle_audio_input = False
    can_handle_image_input = True
    # Natively: `tool_result.content` accepts a list of image blocks.
    can_handle_image_tool_response = True

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_style = ModelStyle.ANTHROPIC
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    def decode_ast(self, result, language, has_tool_call_tag):
        decoded_output = []
        for invoked_function in result:
            name = list(invoked_function.keys())[0]
            params = json.loads(invoked_function[name])
            decoded_output.append({name: params})
        return decoded_output

    def decode_execute(self, result, has_tool_call_tag):
        function_call = convert_to_function_call(result)
        return function_call

    @retry_with_backoff(
        error_type=RateLimitError,
        error_message_pattern=r".*Your credit balance is too low.*",
    )
    def generate_with_backoff(self, **kwargs):
        start_time = time.time()
        api_response = self.client.messages.create(**kwargs)
        end_time = time.time()

        return api_response, end_time - start_time

    def _get_max_tokens(self):
        """
        max_tokens is required to be set when querying, so we default to the model's max tokens
        """
        # https://platform.claude.com/docs/en/about-claude/models/overview
        if "opus" in self.model_name or "sonnet" in self.model_name:
            return 128000
        elif "haiku" in self.model_name:
            return 64000
        else:
            raise ValueError(f"Unsupported model: {self.model_name}")

    #### FC methods ####

    def _query_FC(self, inference_data: dict):
        inference_data["inference_input_log"] = {
            "message": render_messages_for_log(inference_data["message"]),
            "tools": inference_data["tools"],
            "system_prompt": inference_data.get("system_prompt", []),
        }
        messages = inference_data["message"]

        if inference_data["caching_enabled"]:
            if "system_prompt" in inference_data:
                # Cache the system prompt
                inference_data["system_prompt"][0]["cache_control"] = {"type": "ephemeral"}
            # Only add cache control to the last two user messages
            # Remove previously set cache control flags from all user messages except the last two
            #
            # The breakpoint goes on the LAST block of the message, not the first: a
            # cache_control marker ends the cached prefix at that block, so marking
            # block 0 of a multi-block message leaves everything after it out of the
            # cache -- which for a vision turn is the image, i.e. the only part
            # expensive enough to be worth caching.
            count = 0
            for message in reversed(messages):
                if message["role"] != "user":
                    continue
                blocks = [block for block in message["content"] if isinstance(block, dict)]
                for block in blocks:
                    block.pop("cache_control", None)
                if count < 2 and blocks:
                    blocks[-1]["cache_control"] = {"type": "ephemeral"}
                count += 1

        kwargs = {
            "model": self.model_name,
            "max_tokens": self._get_max_tokens(),
            "temperature": self.temperature,
            "tools": inference_data["tools"],
            "messages": messages,
        }

        # Include system_prompt if it exists
        if "system_prompt" in inference_data:
            kwargs["system"] = inference_data["system_prompt"]
        
        # Opus 5 and Sonnet 5 reject sampling params (temperature/top_p/top_k)
        # with a 400; Haiku 4.5 still accepts them.
        if any(m in self.model_name for m in ("opus-5", "sonnet-5")):
            del kwargs["temperature"]

        # Need to set timeout to avoid auto-error when requesting large context length
        # https://github.com/anthropics/anthropic-sdk-python#long-requests
        kwargs["timeout"] = 1200

        return self.generate_with_backoff(**kwargs)

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: dict) -> dict:
        inference_data["message"] = []
        # Claude takes in system prompt in a specific field, not in the message field, so we don't need to add it to the message
        system_prompt = extract_system_prompt(test_entry.conversation[0])
        if system_prompt is not None:
            system_prompt = [{"type": "text", "text": system_prompt}]
            inference_data["system_prompt"] = system_prompt

        test_entry.conversation.map_turns(combine_consecutive_user_prompts)

        # caching enabled only for multi_turn category
        caching_enabled: bool = test_entry.category.contains_multi_step_interaction
        inference_data["caching_enabled"] = caching_enabled

        return inference_data

    def _compile_tools(self, inference_data: dict, test_entry: TestEntry) -> dict:
        tools = convert_to_tool(test_entry.functions, GORILLA_TO_OPENAPI, self.model_style)

        if inference_data["caching_enabled"] and len(tools) > 0:
            # Add the cache control flag to the last tool
            tools[-1]["cache_control"] = {"type": "ephemeral"}

        inference_data["tools"] = tools

        return inference_data

    def _parse_query_response_FC(self, api_response: Any) -> dict:
        text_outputs = []
        tool_call_outputs = []
        tool_call_ids = []

        for content in api_response.content:
            if isinstance(content, TextBlock):
                text_outputs.append(content.text)
            elif isinstance(content, ToolUseBlock):
                tool_call_outputs.append({content.name: json.dumps(content.input)})
                tool_call_ids.append(content.id)

        model_responses = tool_call_outputs if tool_call_outputs else text_outputs

        model_responses_message_for_chat_history = api_response.content

        return {
            "model_responses": model_responses,
            "model_responses_message_for_chat_history": model_responses_message_for_chat_history,
            "tool_call_ids": tool_call_ids,
            "input_token": api_response.usage.input_tokens,
            "output_token": api_response.usage.output_tokens,
        }

    @staticmethod
    def _image_block(image) -> dict:
        return {
            "type": "image",
            "source": {
                "type": "base64",
                # A bare base64 payload -- no `data:` URL prefix, unlike OpenAI's.
                "data": image.image_base64,
                "media_type": image.mime_type,
            },
        }

    def _render_message_content(self, message: Message) -> list[dict]:
        """One message as a list of Anthropic content blocks.

        The text block is emitted only when there is text: ``{"type": "text",
        "text": null}`` passes through the SDK untouched and is rejected by the API.

        Anthropic's vision guide prefers images *before* text. We keep text first
        anyway, so that every provider in the leaderboard receives the same prompt
        structure -- the docs call the difference a soft preference ("images placed
        after text ... still perform well"), and a cross-provider benchmark is worth
        more than a per-provider micro-optimisation.
        """
        content: list[dict] = []
        if message.content:
            content.append({"type": "text", "text": message.content})
        content.extend(self._image_block(image) for image in message.images)
        return content or [{"type": "text", "text": message.content or ""}]

    def add_first_turn_message_FC(
        self, inference_data: dict, first_turn_message: list[Message]
    ) -> dict:
        for message in first_turn_message:
            inference_data["message"].append(
                {
                    "role": message.role.value,
                    "content": self._render_message_content(message),
                }
            )
        return inference_data

    def _add_next_turn_user_message_FC(
        self, inference_data: dict, user_message: list[Message]
    ) -> dict:
        return self.add_first_turn_message_FC(inference_data, user_message)

    def _add_assistant_message_FC(
        self, inference_data: dict, model_response_data: dict
    ) -> dict:
        inference_data["message"].append(
            {
                "role": "assistant",
                "content": model_response_data["model_responses_message_for_chat_history"],
            }
        )
        return inference_data

    def _add_execution_results_FC(
        self,
        inference_data: dict,
        execution_results: list[dict],
        model_response_data: dict,
    ) -> dict:
        # Claude don't use the tool role; it uses the user role to send the tool output
        tool_message = {
            "role": "user",
            "content": [],
        }
        for execution_result, tool_call_id in zip(
            execution_results, model_response_data["tool_call_ids"]
        ):
            if execution_result["result_type"] == ResultType.TEXT:
                tool_message["content"].append(
                    {
                        "type": "tool_result",
                        "content": execution_result["result"],
                        "tool_use_id": tool_call_id,
                    }
                )
            elif execution_result["result_type"] == ResultType.IMAGE:
                tool_message["content"].append(
                    {
                        "type": "tool_result",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "data": execution_result["result"]["image_base64"],
                                    "media_type": execution_result["result"]["type"],
                                },
                            }
                        ],
                        "tool_use_id": tool_call_id,
                    }
                )

        inference_data["message"].append(tool_message)

        return inference_data
