import os
import time
from typing import Any

from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.constants.enums import ModelStyle, ResultType
from bfcl_eval.model_handler.utils import (
    convert_to_tool,
    extract_system_prompt,
    render_messages_for_log,
    retry_with_backoff,
)
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.message import Message, Role
from google import genai
from google.genai.types import (
    AutomaticFunctionCallingConfig,
    Content,
    GenerateContentConfig,
    Part,
    ThinkingConfig,
    Tool,
    FunctionResponsePart,
    FunctionResponseBlob,
)


class GeminiHandler(BaseHandler):
    # Gemini takes audio through the same inline-data part as images -- there is no
    # separate audio helper -- and the documented mp3 mime type is "audio/mp3".
    can_handle_audio_input = True
    can_handle_image_input = True
    # Natively: a function response may carry inline binary parts alongside (or
    # instead of) its JSON payload.
    can_handle_image_tool_response = True

    # The mime type Gemini's audio docs name for mp3. Note it is *not* the IANA
    # spelling "audio/mpeg" (which the API also accepts, but the docs do not use).
    AUDIO_MIME_TYPES = {"mp3": "audio/mp3", "wav": "audio/wav", "flac": "audio/flac"}

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_style = ModelStyle.GOOGLE
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable must be set for Gemini models"
            )
        self.client = genai.Client(api_key=api_key)

    @staticmethod
    def _provider_role(message: Message) -> str:
        # Gemini allows only the roles `user` and `model`.
        return "model" if message.role is Role.ASSISTANT else message.role.value

    def decode_ast(self, result, language, has_tool_call_tag):
        if type(result) is not list:
            result = [result]
        return result

    def decode_execute(self, result, has_tool_call_tag):
        func_call_list = []
        for function_call in result:
            for func_name, func_args in function_call.items():
                func_call_list.append(
                    f"{func_name}({','.join([f'{k}={repr(v)}' for k, v in func_args.items()])})"
                )
        return func_call_list

    # We can't retry on ClientError because it's too broad.
    # Both rate limit and invalid function description will trigger google.genai.errors.ClientError
    @retry_with_backoff(
        error_message_pattern=r".*(RESOURCE_EXHAUSTED|overloaded|experiencing high demand|UNAVAILABLE|Deadline expired|CANCELLED).*"
    )
    def generate_with_backoff(self, **kwargs):
        start_time = time.time()
        api_response = self.client.models.generate_content(**kwargs)
        end_time = time.time()

        return api_response, end_time - start_time

    #### FC methods ####

    def _query_FC(self, inference_data: dict):
        inference_data["inference_input_log"] = {
            "message": render_messages_for_log(inference_data["message"]),
            "tools": inference_data["tools"],
            "system_prompt": inference_data.get("system_prompt", None),
        }

        config = GenerateContentConfig(
            temperature=self.temperature,
            automatic_function_calling=AutomaticFunctionCallingConfig(disable=True),
            thinking_config=ThinkingConfig(include_thoughts=True),
        )

        if "system_prompt" in inference_data:
            config.system_instruction = inference_data["system_prompt"]

        if len(inference_data["tools"]) > 0:
            config.tools = [Tool(function_declarations=inference_data["tools"])]

        return self.generate_with_backoff(
            model=self.model_name,
            contents=inference_data["message"],
            config=config,
        )

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: dict) -> dict:

        inference_data["message"] = []

        system_prompt = extract_system_prompt(test_entry.conversation[0])
        if system_prompt:
            inference_data["system_prompt"] = system_prompt
        return inference_data

    def _compile_tools(self, inference_data: dict, test_entry: TestEntry) -> dict:
        tools = convert_to_tool(test_entry.functions, GORILLA_TO_OPENAPI, self.model_style)

        inference_data["tools"] = tools

        return inference_data

    def _parse_query_response_FC(self, api_response: Any) -> dict:
        tool_call_func_names = []
        fc_parts = []
        text_parts = []
        reasoning_content = []

        if (
            len(api_response.candidates) > 0
            and api_response.candidates[0].content
            and api_response.candidates[0].content.parts
            and len(api_response.candidates[0].content.parts) > 0
        ):
            response_function_call_content = api_response.candidates[0].content

            for part in api_response.candidates[0].content.parts:
                # part.function_call is a FunctionCall object, so it will always be True even if it contains no function call
                # So we need to check if the function name is empty `""` to determine if Gemini returned a function call
                if part.function_call and part.function_call.name:
                    part_func_name = part.function_call.name
                    part_func_args = part.function_call.args
                    part_func_args_dict = {k: v for k, v in part_func_args.items()}

                    fc_parts.append({part_func_name: part_func_args_dict})
                    tool_call_func_names.append(part_func_name)
                # Aggregate reasoning content
                elif part.thought:
                    reasoning_content.append(part.text)
                else:
                    text_parts.append(part.text)

        else:
            response_function_call_content = Content(
                role="model",
                parts=[
                    Part(text="The model did not return any response."),
                ],
            )

        model_responses = fc_parts if fc_parts else text_parts

        return {
            "model_responses": model_responses,
            "model_responses_message_for_chat_history": response_function_call_content,
            "tool_call_func_names": tool_call_func_names,
            "reasoning_content": "\n".join(reasoning_content),
            "input_token": api_response.usage_metadata.prompt_token_count,
            "output_token": api_response.usage_metadata.candidates_token_count,
        }

    def _render_message_parts(self, message: Message) -> list[Part]:
        """One message as a list of Gemini ``Part``s.

        ``Part(text=None)`` is a hard 400 ("required oneof field 'data' must have one
        initialized field"), so the text part is emitted only when there is text --
        which a ``true_audio`` message never has.
        """
        parts: list[Part] = []

        if message.content:
            parts.append(Part(text=message.content))

        for image in message.images:
            parts.append(Part.from_bytes(data=image.image_bytes, mime_type=image.mime_type))

        if message.has_audio:
            parts.append(
                Part.from_bytes(
                    data=message.audio.audio_bytes,
                    mime_type=self.AUDIO_MIME_TYPES.get(
                        message.audio.audio_format, "audio/mp3"
                    ),
                )
            )

        return parts or [Part(text=message.content or "")]

    def add_first_turn_message_FC(
        self, inference_data: dict, first_turn_message: list[Message]
    ) -> dict:
        for message in first_turn_message:
            inference_data["message"].append(
                Content(
                    role=self._provider_role(message),
                    parts=self._render_message_parts(message),
                )
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
        # Tool response needs to be converted to Content object as well.
        # One Content object for all tool responses.
        tool_response_parts = []
        for execution_result, tool_call_func_name in zip(
            execution_results, model_response_data["tool_call_func_names"]
        ):
            if execution_result["result_type"] == ResultType.TEXT:
                tool_response_parts.append(
                    Part.from_function_response(
                        name=tool_call_func_name,
                        response={
                            "result": execution_result["result"],
                        },
                    )
                )
            elif execution_result["result_type"] == ResultType.IMAGE:
                tool_response_parts.append(
                    Part.from_function_response(
                        name=tool_call_func_name,
                        response={},
                        parts=[
                            FunctionResponsePart(
                                inline_data=FunctionResponseBlob(
                                    data=execution_result["result"]["image_bytes"],
                                    mime_type=execution_result["result"]["type"],
                                ),
                            )
                        ],
                    )
                )

        tool_response_content = Content(role="user", parts=tool_response_parts)
        inference_data["message"].append(tool_response_content)

        return inference_data
