import json
import time
from typing import Any

import requests
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.constants.enums import ModelStyle
from bfcl_eval.model_handler.utils import ast_parse
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.message import Message


class GorillaHandler(BaseHandler):
    # Gorilla OpenFunctions is a text-in/text-out function-calling model served over a
    # plain JSON endpoint: messages are `{"role", "content"}` with a string body, and
    # there is no content-part vocabulary to carry anything else.
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
        self.model_style = ModelStyle.GORILLA

    def decode_ast(self, result, language, has_tool_call_tag):
        func = "[" + result + "]"
        decoded_output = ast_parse(func, language, has_tool_call_tag)
        return decoded_output

    def decode_execute(self, result, has_tool_call_tag):
        func = "[" + result + "]"
        decoded_output = ast_parse(func, has_tool_call_tag)
        execution_list = []
        for function_call in decoded_output:
            for key, value in function_call.items():
                execution_list.append(
                    f"{key}({','.join([f'{k}={repr(v)}' for k, v in value.items()])})"
                )
        return execution_list

    #### FC methods ####

    def _query_FC(self, inference_data: dict):
        inference_data["inference_input_log"] = {
            "message": inference_data["message"],
            "tools": inference_data["tools"],
        }
        requestData = {
            "model": self.model_name,
            "messages": inference_data["message"],
            "functions": inference_data["tools"],
            "temperature": self.temperature,
        }
        url = "https://luigi.millennium.berkeley.edu:443/v1/chat/completions"

        start_time = time.time()
        api_response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "EMPTY",  # Hosted for free with ❤️ from UC Berkeley
            },
            data=json.dumps(requestData),
        )
        end_time = time.time()

        return api_response.json(), end_time - start_time

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: dict) -> dict:
        inference_data["message"] = []
        return inference_data

    def _compile_tools(self, inference_data: dict, test_entry: TestEntry) -> dict:
        # Gorilla OpenFunctions does not require any pre-processing
        inference_data["tools"] = [doc.to_dict() for doc in test_entry.functions]

        return inference_data

    def _parse_query_response_FC(self, api_response: Any) -> dict:

        return {
            "model_responses": api_response["choices"][0]["message"]["content"],
            "input_token": api_response["usage"]["prompt_tokens"],
            "output_token": api_response["usage"]["completion_tokens"],
        }

    def add_first_turn_message_FC(
        self, inference_data: dict, first_turn_message: list[Message]
    ) -> dict:
        # Text only, and `content` is never None here: the base handler refuses a turn
        # carrying audio or images before it reaches this method.
        inference_data["message"].extend(
            {"role": message.role.value, "content": message.content or ""}
            for message in first_turn_message
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
                "content": model_response_data["model_responses"],
            }
        )
        return inference_data

    def _add_execution_results_FC(
        self, inference_data: dict, execution_results: list[dict], model_response_data: dict
    ) -> dict:
        for execution_result in execution_results:
            tool_message = {
                "role": "tool",
                "content": execution_result["result"],
            }
            inference_data["message"].append(tool_message)

        return inference_data
