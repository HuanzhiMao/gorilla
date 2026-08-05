import json
import os
import time

from bfcl_eval.constants.enums import ModelStyle, ResultType
from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.model_handler.utils import (
    convert_to_function_call,
    convert_to_tool,
    render_messages_for_log,
    retry_with_backoff,
)
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.message import Message, Role
from openai import OpenAI, RateLimitError
from openai.types.responses import Response


class OpenAIResponsesHandler(BaseHandler):
    # The Responses input union is text / image / file -- no audio member. OpenAI's
    # audio guide redirects to Chat Completions with an audio-capable model, and the
    # audio models are marked "not supported" on Responses.
    can_handle_audio_input = False
    can_handle_image_input = True
    # Natively, and unlike Chat Completions: `function_call_output.output` accepts a
    # list of input_text / input_image / input_file parts.
    can_handle_image_tool_response = True

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_style = ModelStyle.OPENAI_RESPONSES
        self.client = OpenAI(**self._build_client_kwargs())

    def _build_client_kwargs(self):
        """Collect OpenAI client keyword arguments from environment variables, but only
        include them if they are actually present so that we keep the call minimal
        and rely on the OpenAI SDK's own defaults when possible."""

        kwargs = {"base_url": "https://us.api.openai.com/v1"}

        if api_key := os.getenv("OPENAI_API_KEY"):
            kwargs["api_key"] = api_key

        if base_url := os.getenv("OPENAI_BASE_URL"):
            kwargs["base_url"] = base_url

        if headers_env := os.getenv("OPENAI_DEFAULT_HEADERS"):
            kwargs["default_headers"] = json.loads(headers_env)

        return kwargs

    @staticmethod
    def _provider_role(message: Message) -> str:
        # OpenAI allows `system` role in the prompt, but it is meant for "messages added
        # by OpenAI"; for our use case `developer` is recommended instead.
        # See https://model-spec.openai.com/2025-04-11.html#definitions
        return "developer" if message.role is Role.SYSTEM else message.role.value

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
        # print(kwargs)
        api_response = self.client.responses.create(**kwargs)
        end_time = time.time()

        return api_response, end_time - start_time

    #### FC methods ####

    def _query_FC(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        tools = inference_data["tools"]

        inference_data["inference_input_log"] = {
            "message": render_messages_for_log(message),
            "tools": tools,
        }

        kwargs = {
            "input": message,
            "model": self.model_name,
            "store": False,
            "include": ["reasoning.encrypted_content"],
            "reasoning": {"summary": "auto"},
            "temperature": self.temperature,
        }

        # OpenAI reasoning models don't support temperature parameter
        if (
            "o3" in self.model_name
            or "o4-mini" in self.model_name
            or "gpt-5" in self.model_name
        ):
            del kwargs["temperature"]

        # Non-reasoning models don't support reasoning parameter
        else:
            del kwargs["reasoning"]
            del kwargs["include"]

        if len(tools) > 0:
            kwargs["tools"] = tools

        return self.generate_with_backoff(**kwargs)

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: TestEntry) -> dict:
        inference_data["message"] = []

        return inference_data

    def _compile_tools(self, inference_data: dict, test_entry: TestEntry) -> dict:
        tools = convert_to_tool(test_entry.functions, GORILLA_TO_OPENAPI, self.model_style)

        inference_data["tools"] = tools

        return inference_data

    def _parse_query_response_FC(self, api_response: Response) -> dict:
        model_responses = []
        tool_call_ids = []

        for func_call in api_response.output:
            if func_call.type == "function_call":
                model_responses.append({func_call.name: func_call.arguments})
                tool_call_ids.append(func_call.call_id)

        if not model_responses:  # If there are no function calls
            model_responses = api_response.output_text

        # OpenAI reasoning models don't show full reasoning content in the api response,
        # but only a summary of the reasoning content.
        reasoning_content = ""
        for item in api_response.output:
            if item.type == "reasoning":
                for summary in item.summary:
                    reasoning_content += summary.text + "\n"

        return {
            "model_responses": model_responses,
            "model_responses_message_for_chat_history": api_response.output,
            "tool_call_ids": tool_call_ids,
            "reasoning_content": reasoning_content,
            "input_token": api_response.usage.input_tokens,
            "output_token": api_response.usage.output_tokens,
        }

    @staticmethod
    def _image_part(mime_type: str, image_base64: str) -> dict:
        # Three things differ from Chat Completions and all three are load-bearing:
        # the part type is `input_image`, the sibling text type is `input_text`, and
        # `image_url` is a bare string rather than an object with a `url` key.
        #
        # `detail` is spelled out rather than left to the API's default because the
        # same part is used in two positions with two generated types:
        # `ResponseInputImageParam` (message content) marks it Required, while
        # `ResponseInputImageContentParam` (function_call_output) marks it Optional.
        # "auto" is the value the API would have picked anyway.
        return {
            "type": "input_image",
            "image_url": f"data:{mime_type};base64,{image_base64}",
            "detail": "auto",
        }

    def _render_message_content(self, message: Message) -> list[dict]:
        """One message as a Responses content-part list, text first.

        Text leads for consistency with every other handler here, so the leaderboard
        compares providers on the same prompt structure. The empty-text part is
        dropped: this API has no audio input, so a content-less message can only be a
        degenerate one, and `{"type": "input_text", "text": null}` is not valid.
        """
        content: list[dict] = []
        if message.content:
            content.append({"type": "input_text", "text": message.content})
        content.extend(
            self._image_part(image.mime_type, image.image_base64)
            for image in message.images
        )
        return content or [{"type": "input_text", "text": message.content or ""}]

    def add_first_turn_message_FC(
        self, inference_data: dict, first_turn_message: list[Message]
    ) -> dict:
        for message in first_turn_message:
            inference_data["message"].append(
                {
                    "role": self._provider_role(message),
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
        inference_data["message"].extend(
            model_response_data["model_responses_message_for_chat_history"]
        )
        return inference_data

    def _add_execution_results_FC(
        self,
        inference_data: dict,
        execution_results: list[dict],
        model_response_data: dict,
    ) -> dict:
        # Add the execution results to the current round result, one at a time
        for execution_result, tool_call_id in zip(
            execution_results, model_response_data["tool_call_ids"]
        ):
            if execution_result["result_type"] == ResultType.IMAGE:
                image = execution_result["result"]
                # A list of content parts is a documented `output` value here, so no
                # placeholder-plus-user-message dance is needed.
                output = [
                    self._image_part(
                        image.get("type", "image/jpeg"), image["image_base64"]
                    )
                ]
            else:
                output = execution_result["result"]

            inference_data["message"].append(
                {
                    "type": "function_call_output",
                    "call_id": tool_call_id,
                    "output": output,
                }
            )

        return inference_data
