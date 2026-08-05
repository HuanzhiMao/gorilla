import json
import os
import time
from typing import Any

from bfcl_eval.constants.default_prompts import (
    VISION_TOOL_RESPONSE_TEXT_PROMPT,
    VISION_TOOL_RESPONSE_USER_MESSAGE_PREFIX,
)
from bfcl_eval.constants.enums import ModelStyle, ResultType
from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.model_handler.utils import (
    convert_to_function_call,
    convert_to_tool,
    image_content_from_execution_result,
    render_messages_for_log,
    retry_with_backoff,
)
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.message import ImageContent, Message, Role
from openai import OpenAI, RateLimitError


class OpenAICompletionsHandler(BaseHandler):
    # These say what the *protocol* can carry, not what any one model accepts -- the
    # per-model gate is `supports_audio_input` / `supports_image_input` in
    # `model_config.py`. Chat Completions defines an `input_audio` content part, so
    # every vendor speaking this protocol (and vLLM) can be handed audio; whether the
    # model on the other end understands it is the registry's business.
    can_handle_audio_input = True
    can_handle_image_input = True
    # Not natively: a Chat Completions `tool` message is text-only. The handler
    # emulates it with a text placeholder plus a trailing user message that carries
    # the bytes, which is the documented workaround -- so the image does reach the
    # model, which is what this flag promises.
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
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = OpenAI(**self._build_client_kwargs())
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    def _build_client_kwargs(self):
        """Collect OpenAI client keyword arguments from environment variables, but only
        include them if they are actually present so that we keep the call minimal
        and rely on the OpenAI SDK's own defaults when possible."""

        kwargs = {}

        if api_key := os.getenv("OPENAI_API_KEY"):
            kwargs["api_key"] = api_key

        if base_url := os.getenv("OPENAI_BASE_URL"):
            kwargs["base_url"] = base_url

        if headers_env := os.getenv("OPENAI_DEFAULT_HEADERS"):
            kwargs["default_headers"] = json.loads(headers_env)

        return kwargs

    def decode_ast(self, result, language, has_tool_call_tag):
        decoded_output = []
        for invoked_function in result:
            name = list(invoked_function.keys())[0]
            params = json.loads(invoked_function[name])
            decoded_output.append({name: params})
        return decoded_output

    def decode_execute(self, result, has_tool_call_tag):
        return convert_to_function_call(result)

    @retry_with_backoff(error_type=RateLimitError)
    def generate_with_backoff(self, **kwargs):
        start_time = time.time()
        api_response = self.client.chat.completions.create(**kwargs)
        end_time = time.time()

        return api_response, end_time - start_time

    #### FC methods ####

    def _query_FC(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        tools = inference_data["tools"]
        inference_data["inference_input_log"] = {"message": render_messages_for_log(message), "tools": tools}

        kwargs = {
            "messages": message,
            "model": self.model_name,
            "temperature": self.temperature,
            "store": False,
        }

        if len(tools) > 0:
            kwargs["tools"] = tools

        return self.generate_with_backoff(**kwargs)

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: dict) -> dict:
        inference_data["message"] = []
        return inference_data

    def _compile_tools(self, inference_data: dict, test_entry: TestEntry) -> dict:
        tools = convert_to_tool(test_entry.functions, GORILLA_TO_OPENAPI, self.model_style)

        inference_data["tools"] = tools

        return inference_data

    def _parse_query_response_FC(self, api_response: Any) -> dict:
        if api_response.choices[0].message.tool_calls:
            tool_calls = api_response.choices[0].message.tool_calls
            model_responses = [
                {func_call.function.name: func_call.function.arguments}
                for func_call in tool_calls
            ]
            tool_call_ids = [func_call.id for func_call in tool_calls]
        else:
            model_responses = api_response.choices[0].message.content
            tool_call_ids = []

        model_responses_message_for_chat_history = api_response.choices[0].message

        response_data = {
            "model_responses": model_responses,
            "model_responses_message_for_chat_history": model_responses_message_for_chat_history,
            "tool_call_ids": tool_call_ids,
            "input_token": api_response.usage.prompt_tokens,
            "output_token": api_response.usage.completion_tokens,
        }
        self._add_reasoning_content_if_available_FC(api_response, response_data)
        return response_data

    def _render_message_content(self, message: Message) -> list[dict]:
        """One user/system message as a Chat Completions content-part list.

        Text first, then images, then audio -- the order OpenAI's vision guide uses.
        The text part is omitted when there is none: a ``true_audio`` entry carries no
        ``content`` at all, and ``{"type": "text", "text": None}`` is a 400.

        Note the two encodings are deliberately different, and both are required:
        an image is a full ``data:`` URL, an audio payload is bare base64.
        """
        content: list[dict] = []

        if message.content:
            content.append({"type": "text", "text": message.content})

        for image in message.images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{image.mime_type};base64,{image.image_base64}"
                    },
                }
            )

        if message.has_audio:
            content.append(
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": message.audio.base64(),
                        # The API accepts "wav" and "mp3" only; BFCL audio is mp3.
                        "format": message.audio.audio_format,
                    },
                }
            )

        # A message with nothing in it at all would be rejected; keep the empty string.
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
            model_response_data["model_responses_message_for_chat_history"]
        )
        return inference_data

    def _add_execution_results_FC(
        self,
        inference_data: dict,
        execution_results: list[dict],
        model_response_data: dict,
    ) -> dict:
        # A Chat Completions `tool` message may only carry text -- its content type is
        # narrowed to ChatCompletionContentPartText, unlike a user message's. So an
        # image tool result is delivered in two parts: a text placeholder that closes
        # out the tool_call_id, and one trailing user message carrying every image
        # produced this round.
        image_note = VISION_TOOL_RESPONSE_USER_MESSAGE_PREFIX
        tool_response_images: list[ImageContent] = []

        # Add the execution results to the current round result, one at a time
        for execution_result, tool_call_id in zip(
            execution_results, model_response_data["tool_call_ids"]
        ):
            if execution_result["result_type"] == ResultType.IMAGE:
                image_note += (
                    f"Tool response for tool call id {tool_call_id} is an image, "
                    f"attached below. "
                )
                tool_response_images.append(
                    image_content_from_execution_result(execution_result)
                )
                content = VISION_TOOL_RESPONSE_TEXT_PROMPT
            else:
                content = execution_result["result"]

            inference_data["message"].append(
                {
                    "role": "tool",
                    "content": content,
                    "tool_call_id": tool_call_id,
                }
            )

        if tool_response_images:
            inference_data = self._add_next_turn_user_message_FC(
                inference_data,
                [Message(role=Role.USER, content=image_note, images=tool_response_images)],
            )

        return inference_data

    def _add_reasoning_content_if_available_FC(
        self, api_response: Any, response_data: dict
    ) -> None:
        """
        OpenAI models don't show reasoning content in the api response,
        but many other models that use the OpenAI interface do, such as DeepSeek and Grok.
        This method is included here to avoid code duplication.

        These models often don't take reasoning content in the chat history for next turn.
        Thus, this method saves reasoning content to response_data (for local result file) if present in the response,
        but does not include it in the chat history.
        """
        # Original assistant message object (contains `reasoning_content` on DeepSeek).
        message = api_response.choices[0].message

        # Preserve tool_call information but strip the unsupported `reasoning_content` field before inserting into chat history.
        if getattr(message, "tool_calls", None):
            assistant_message = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": tool_call.type,
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    }
                    for tool_call in message.tool_calls
                ],
            }
            response_data["model_responses_message_for_chat_history"] = assistant_message

        # If no tool_calls, we still need to strip reasoning_content.
        elif hasattr(message, "reasoning_content"):
            response_data["model_responses_message_for_chat_history"] = {
                "role": "assistant",
                "content": message.content,
            }

        # Capture the reasoning trace so it can be logged to the local result file.
        if hasattr(message, "reasoning_content"):
            response_data["reasoning_content"] = message.reasoning_content

        # vllm might use `reasoning` instead of `reasoning_content`
        if hasattr(message, "reasoning"):
            response_data["reasoning_content"] = message.reasoning
