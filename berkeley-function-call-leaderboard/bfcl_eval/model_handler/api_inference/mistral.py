import json
import os
import time
from typing import Any

from bfcl_eval.constants.default_prompts import VISION_TOOL_RESPONSE_TEXT_PROMPT
from bfcl_eval.constants.enums import ModelStyle, ResultType
from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.model_handler.utils import (
    convert_to_function_call,
    convert_to_tool,
    image_content_from_execution_result,
    retry_with_backoff,
)
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.message import ImageContent, Message, Role
from mistralai.client import Mistral


class MistralHandler(BaseHandler):
    # Mistral does define an `input_audio` chunk, but only the Voxtral family accepts
    # it -- and this handler serves `mistral-large-2512`, which does not. (The shape
    # also differs from OpenAI's: a bare base64 string, with no `format` field.) The
    # self-hosted Mistral checkpoints in the registry go through OSSHandler, not here.
    can_handle_audio_input = False
    can_handle_image_input = True
    # Not natively: an image chunk inside a `tool` message is schema-legal in the SDK
    # but is not a documented model behaviour anywhere. The handler uses the pattern
    # the docs do exercise -- a text tool result, then a user message carrying the
    # image -- so the bytes still reach the model.
    can_handle_image_tool_response = True

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_style = ModelStyle.MISTRAL

        self.client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))

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

    @retry_with_backoff(error_message_pattern=r".*Status 429.*")
    def generate_with_backoff(self, **kwargs):
        start_time = time.time()
        api_response = self.client.chat.complete(**kwargs)
        end_time = time.time()

        return api_response, end_time - start_time

    #### FC methods ####

    def _query_FC(self, inference_data: dict):
        message = inference_data["message"]
        tool = inference_data["tools"]
        inference_data["inference_input_log"] = {
            "message": message,
            "tools": tool,
        }

        return self.generate_with_backoff(
            model=self.model_name,
            messages=message,
            tools=tool,
            temperature=self.temperature,
        )

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: dict) -> dict:
        inference_data["message"] = []
        return inference_data

    def _compile_tools(self, inference_data: dict, test_entry: TestEntry) -> dict:
        tools = convert_to_tool(test_entry.functions, GORILLA_TO_OPENAPI, self.model_style)

        inference_data["tools"] = tools

        return inference_data

    def _parse_query_response_FC(self, api_response: Any) -> dict:
        try:
            model_responses = [
                {func_call.function.name: func_call.function.arguments}
                for func_call in api_response.choices[0].message.tool_calls
            ]
            tool_call_func_names = [
                func_call.function.name
                for func_call in api_response.choices[0].message.tool_calls
            ]
            tool_call_ids = [
                func_call.id for func_call in api_response.choices[0].message.tool_calls
            ]
        except:
            model_responses = api_response.choices[0].message.content
            tool_call_func_names = []
            tool_call_ids = []

        return {
            "model_responses": model_responses,
            "model_responses_message_for_chat_history": api_response.choices[0].message,
            "tool_call_func_names": tool_call_func_names,
            "tool_call_ids": tool_call_ids,
            "input_token": api_response.usage.prompt_tokens,
            "output_token": api_response.usage.completion_tokens,
        }

    @staticmethod
    def _image_chunk(mime_type: str, image_base64: str) -> dict:
        # `image_url` is a union of a bare data-URI string and an object with a `url`
        # key; the official sample uses the bare string, so we do too.
        return {
            "type": "image_url",
            "image_url": f"data:{mime_type};base64,{image_base64}",
        }

    def _render_message_content(self, message: Message) -> str | list[dict]:
        """One message as Mistral chunks, or a bare string when it is text-only.

        The bare string is deliberate: it is what Mistral's own examples send, and
        keeping it avoids wrapping every text turn in a one-element list. The text
        chunk is skipped when there is no text -- ``TextChunk(text=None)`` fails
        pydantic validation inside the SDK before any request is made.
        """
        if not message.images:
            return message.content or ""

        content: list[dict] = []
        if message.content:
            content.append({"type": "text", "text": message.content})
        content.extend(
            self._image_chunk(image.mime_type, image.image_base64)
            for image in message.images
        )
        return content

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
        self, inference_data: dict, execution_results: list[dict], model_response_data: dict
    ) -> dict:
        image_note = ""
        tool_response_images: list[ImageContent] = []

        for execution_result, func_name, tool_call_id in zip(
            execution_results,
            model_response_data["tool_call_func_names"],
            model_response_data["tool_call_ids"],
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
                    "name": func_name,
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
