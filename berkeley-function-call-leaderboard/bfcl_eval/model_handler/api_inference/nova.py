import os
import time
from typing import Any

import boto3
from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.constants.enums import ModelStyle, ResultType
from bfcl_eval.model_handler.utils import (
    combine_consecutive_user_prompts,
    convert_to_function_call,
    convert_to_tool,
    extract_system_prompt,
    render_messages_for_log,
    retry_with_backoff,
)
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.message import Message


class NovaHandler(BaseHandler):
    # Converse does define an `audio` content block (mp3 among its formats) and boto3
    # will serialize one happily -- but no Nova model accepts it. Nova's speech support
    # is Nova Sonic, which is a separate bidirectional-streaming API, not Converse. So
    # the handler declines rather than sending a block that is only schema-valid.
    can_handle_audio_input = False
    can_handle_image_input = True
    # Natively: `toolResult.content` takes the same image block a user message does.
    can_handle_image_tool_response = True

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_style = ModelStyle.AMAZON
        _session = boto3.Session(
            profile_name=os.getenv("AWS_SSO_PROFILE_NAME"), region_name="us-east-1"
        )
        self.client = _session.client(service_name="bedrock-runtime")

    def decode_ast(self, result, language, has_tool_call_tag):
        if type(result) != list:
            raise ValueError(f"Model did not return a list of function calls: {result}")
        return result

    def decode_execute(self, result, has_tool_call_tag):
        if type(result) != list:
            raise ValueError(f"Model did not return a list of function calls: {result}")
        return convert_to_function_call(result)

    @retry_with_backoff(error_message_pattern=r".*\(ThrottlingException\).*")
    def generate_with_backoff(self, **kwargs):
        start_time = time.time()
        api_response = self.client.converse(**kwargs)
        end_time = time.time()

        return api_response, end_time - start_time

    #### FC methods ####

    def _query_FC(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        tools = inference_data["tools"]

        if "system_prompt" in inference_data:
            system_prompt = inference_data["system_prompt"]
        else:
            system_prompt = []

        inference_data["inference_input_log"] = {
            "message": render_messages_for_log(message),
            "tools": tools,
            "system_prompt": system_prompt,
        }

        kwargs = {
            "modelId": self.model_name,
            "messages": message,
            "system": system_prompt,
            "inferenceConfig": {"temperature": self.temperature},
        }
        if len(tools) > 0:
            kwargs["toolConfig"] = {"tools": tools}

        if "nova-2-lite" in self.model_name:
            kwargs["additionalModelRequestFields"] = {
                "reasoningConfig": {"type": "enabled", "maxReasoningEffort": "medium"}
            }

        return self.generate_with_backoff(**kwargs)

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: dict) -> dict:
        test_entry.conversation.map_turns(combine_consecutive_user_prompts)

        inference_data["message"] = []

        system_prompt = extract_system_prompt(test_entry.conversation[0])
        if system_prompt:
            inference_data["system_prompt"] = [{"text": system_prompt}]

        return inference_data

    def _compile_tools(self, inference_data: dict, test_entry: TestEntry) -> dict:
        tools = convert_to_tool(test_entry.functions, GORILLA_TO_OPENAPI, self.model_style)

        inference_data["tools"] = tools

        return inference_data

    def _parse_query_response_FC(self, api_response: Any) -> dict:
        model_responses_message_for_chat_history = api_response["output"]["message"]
        reasoning_content = ""

        text_parts = []
        tool_parts = []
        tool_call_ids = []
        for func_call in api_response["output"]["message"]["content"]:
            if "reasoningContent" in func_call:
                reasoning_content += func_call["reasoningContent"]["reasoningText"]["text"]

            elif "text" in func_call:
                text_parts.append(func_call["text"])

            elif "toolUse" in func_call:
                func_call = func_call["toolUse"]
                func_name = func_call["name"]
                func_args = func_call["input"]
                tool_parts.append({func_name: func_args})
                tool_call_ids.append(func_call["toolUseId"])

        return {
            "model_responses": tool_parts if tool_parts else text_parts,
            "model_responses_message_for_chat_history": model_responses_message_for_chat_history,
            "tool_call_ids": tool_call_ids,
            "reasoning_content": reasoning_content,
            "input_token": api_response["usage"]["inputTokens"],
            "output_token": api_response["usage"]["outputTokens"],
        }

    @staticmethod
    def _image_block(mime_type: str, image_bytes: bytes) -> dict:
        return {
            "image": {
                # Converse wants a bare format token ("jpeg"), not a mime type.
                "format": mime_type.split("/")[-1],
                # Raw bytes: botocore base64-encodes the blob on the way out.
                "source": {"bytes": image_bytes},
            }
        }

    def _render_message_content(self, message: Message) -> list[dict]:
        """One message as Converse content blocks.

        botocore validates client-side, so a ``{"text": None}`` block never reaches
        AWS -- it raises ParamValidationError locally instead. Omit it when empty.
        """
        content: list[dict] = []
        if message.content:
            content.append({"text": message.content})
        content.extend(
            self._image_block(image.mime_type, image.image_bytes)
            for image in message.images
        )
        return content or [{"text": message.content or ""}]

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
        self, inference_data: dict, user_message: list[dict]
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
        # Nova use the `user` role for the tool result message
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
                        "toolResult": {
                            "toolUseId": tool_call_id,
                            "content": [{"text": execution_result["result"]}],
                        }
                    }
                )
            elif execution_result["result_type"] == ResultType.IMAGE:
                image = execution_result["result"]
                tool_message["content"].append(
                    {
                        "toolResult": {
                            "toolUseId": tool_call_id,
                            "content": [
                                self._image_block(
                                    image.get("type", "image/jpeg"), image["image_bytes"]
                                )
                            ],
                        }
                    }
                )

        inference_data["message"].append(tool_message)

        return inference_data
