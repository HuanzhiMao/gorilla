import ast
import json
import os
import time
from typing import Any

import cohere
from bfcl_eval.constants.default_prompts import VISION_TOOL_RESPONSE_TEXT_PROMPT
from bfcl_eval.constants.enums import ModelStyle, ResultType
from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.model_handler.utils import (
    convert_to_tool,
    extract_system_prompt,
    image_content_from_execution_result,
    retry_with_backoff,
)
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.message import ImageContent, Message, Role
from tenacity.stop import stop_after_attempt


class CohereHandler(BaseHandler):
    # Cohere Chat v2 has no audio content type of any kind.
    can_handle_audio_input = False
    # It does take images: Chat v2 user messages accept an `image_url` content part
    # (Command A Vision and later). Whether a given Cohere model reads them is the
    # registry's call, via `supports_image_input`.
    can_handle_image_input = True
    # Not natively -- a `tool` message may only hold text or document blocks -- so the
    # image travels in a following user message, as on OpenAI Chat Completions.
    can_handle_image_tool_response = True

    client: cohere.ClientV2

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_style = ModelStyle.COHERE
        self.client = cohere.ClientV2(api_key=os.getenv("COHERE_API_KEY"))

    def decode_ast(self, result, language, has_tool_call_tag):
        decoded_output = []
        if isinstance(result, list):
            for tool_call in result:
                decoded_output.append({tool_call["tool_name"]: tool_call["parameters"]})
        return decoded_output

    def decode_execute(self, result, has_tool_call_tag):
        execution_list = []
        if isinstance(result, list):
            for tool_call in result:
                args = ",".join(
                    f"{name}={value!r}" for name, value in tool_call["parameters"].items()
                )
                execution_list.append("{}({})".format(tool_call["tool_name"], args))
        return execution_list

    #### FC methods ####

    def _query_FC(self, inference_data: dict):
        messages = []
        if system_message := inference_data.get("system_message"):
            messages.append({"role": "system", "content": system_message})
        messages.extend(inference_data["chat_turns"])

        response, latency = self.generate_with_backoff(
            messages=messages,
            tools=inference_data["tools"],
        )

        response_message = response.message

        # Append the assistant turn (tool_plan, tool_calls and content) back into the
        # history verbatim, as the documented tool-use loop does. We normalize it to a
        # dict so the whole history stays uniformly subscriptable.
        inference_data["chat_turns"].append(response_message.model_dump(exclude_none=True))

        tool_calls = [
            {
                "tool_name": tool_call.function.name,
                "parameters": json.loads(tool_call.function.arguments),
            }
            for tool_call in (response_message.tool_calls or [])
        ]

        # Reasoning models return "thinking" blocks alongside "text" blocks; dispatch on
        # the block's `type` discriminator rather than on SDK class identity.
        text_parts, thinking_parts = [], []
        for block in response_message.content or []:
            if block.type == "thinking":
                thinking_parts.append(block.thinking)
            elif block.type == "text":
                text_parts.append(block.text)

        input_token, output_token = 0, 0
        if response.usage and response.usage.billed_units:
            input_token = response.usage.billed_units.input_tokens or 0
            output_token = response.usage.billed_units.output_tokens or 0

        metadata = {
            "text": "\n".join(text_parts),
            "reasoning_content": "".join(thinking_parts),
            "tool_calls": tool_calls,
            "input_token": input_token,
            "output_token": output_token,
        }
        return metadata, latency

    @retry_with_backoff(error_type=Exception, stop=stop_after_attempt(5), reraise=True)
    def generate_with_backoff(
        self, messages: list[dict], tools: list[dict]
    ) -> tuple[Any, float]:
        start_time = time.time()
        api_response = self.client.chat(
            model=self.model_name,
            messages=messages,
            tools=tools,
            citation_options={"mode": "OFF"},
            temperature=self.temperature,
        )
        end_time = time.time()

        return api_response, end_time - start_time

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: TestEntry) -> dict:
        # We only extract the system message from the first turn.
        system_message = extract_system_prompt(test_entry.conversation[0])
        if system_message:
            inference_data["system_message"] = system_message
        return inference_data

    def _compile_tools(self, inference_data: dict, test_entry: TestEntry) -> dict:
        tools = convert_to_tool(test_entry.functions, GORILLA_TO_OPENAPI, self.model_style)
        inference_data["tools"] = [_to_cohere_tool(tool) for tool in tools]

        return inference_data

    def _parse_query_response_FC(self, api_response: Any) -> dict:
        # A turn is either tool calls or a text answer, never both.
        tool_calls = api_response["tool_calls"]
        return {
            "model_responses": tool_calls if tool_calls else api_response["text"],
            "reasoning_content": api_response["reasoning_content"] or None,
            "tool_calls": tool_calls,
            "chat_history": [],
            "input_token": api_response["input_token"],
            "output_token": api_response["output_token"],
        }

    def add_first_turn_message_FC(
        self, inference_data: dict, first_turn_message: list[Message]
    ) -> dict:
        inference_data["chat_turns"] = [
            _to_cohere_message(message) for message in first_turn_message
        ]
        inference_data["raw_prompt"] = []
        inference_data["raw_completion"] = []
        return inference_data

    def _add_next_turn_user_message_FC(
        self, inference_data: dict, user_message: list[Message]
    ) -> dict:
        assert "chat_turns" in inference_data, "expected chat_turns to be present"
        chat_turns = inference_data["chat_turns"]
        for message in user_message:
            chat_turns.append(_to_cohere_message(message))
        if chat_turns[-1]["role"] != "user":
            # The conversation must end on a user turn for the model to respond to it.
            chat_turns.append({"role": "user", "content": ""})
        return inference_data

    def _add_assistant_message_FC(
        self, inference_data: dict, model_response_data: dict
    ) -> dict:
        # Already appended verbatim in _query_FC, so there is nothing to add here.
        return inference_data

    def _add_execution_results_FC(
        self, inference_data: dict, execution_results: list[dict], model_response_data: dict
    ) -> dict:
        if not execution_results:
            return inference_data

        # Non-empty execution_results means the last turn must have been a tool-call turn.
        last_turn = inference_data["chat_turns"][-1]
        assert (
            last_turn["role"] == "assistant"
        ), "last turn must be tool use turn and from the assistant"
        tool_calls = last_turn.get("tool_calls")
        assert tool_calls, "last turn must have tool calls"
        assert len(tool_calls) == len(
            execution_results
        ), "Number of execution result must match number of tool calls from last turn!"

        image_note = ""
        tool_response_images: list[ImageContent] = []

        for tool_call, execution_result in zip(tool_calls, execution_results):
            if execution_result["result_type"] == ResultType.IMAGE:
                # A Cohere tool message carries text or documents, never an image, so
                # the bytes go out in the user message appended below.
                image_note += (
                    f"Tool response for tool call id {tool_call['id']} is an image, "
                    f"attached below. "
                )
                tool_response_images.append(
                    image_content_from_execution_result(execution_result)
                )
                text = VISION_TOOL_RESPONSE_TEXT_PROMPT
            else:
                text = _render_result(execution_result["result"])

            inference_data["chat_turns"].append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": [{"type": "text", "text": text}],
                }
            )

        if tool_response_images:
            inference_data = self._add_next_turn_user_message_FC(
                inference_data,
                [Message(role=Role.USER, content=image_note, images=tool_response_images)],
            )
        return inference_data


def _render_result(result_str: str) -> str:
    """Render an execution result for the tool message content."""
    try:
        result = ast.literal_eval(result_str)
    except Exception:
        return result_str
    if isinstance(result, dict):
        if "id" in result:
            # `id` is reserved by Cohere's document handling; surface it as `ID` instead.
            result["ID"] = result.pop("id")
        return json.dumps(result)
    return result_str


def _to_cohere_message(message: Message) -> dict:
    role = message.role.value
    assert role in ("user", "assistant"), "message role must be in ['user', 'assistant']"

    if not message.images:
        return {"role": role, "content": message.content or ""}

    content: list[dict] = []
    if message.content:
        content.append({"type": "text", "text": message.content})
    content.extend(
        {
            "type": "image_url",
            # Chat v2 wants an object with a `url` key, holding a data URI.
            "image_url": {"url": f"data:{image.mime_type};base64,{image.image_base64}"},
        }
        for image in message.images
    )
    return {"role": role, "content": content}


def _to_cohere_tool(tool: dict) -> dict:
    function = tool["function"]
    return {
        "type": "function",
        "function": {
            "name": function["name"],
            "description": function["description"],
            "parameters": function["parameters"],
        },
    }
