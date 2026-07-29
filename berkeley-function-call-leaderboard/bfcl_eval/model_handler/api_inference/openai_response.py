import json
import os
import time

from bfcl_eval.constants.enums import ModelStyle, ResultType
from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.model_handler.utils import (
    convert_to_function_call,
    convert_to_tool,
    retry_with_backoff,
)
from openai import OpenAI, RateLimitError
from openai.types.responses import Response


class OpenAIResponsesHandler(BaseHandler):
    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        is_fc_model,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, is_fc_model, **kwargs)
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
    def _substitute_prompt_role(prompts: list[dict]) -> list[dict]:
        # OpenAI allows `system` role in the prompt, but it is meant for "messages added by OpenAI"
        # For our use case, it is recommended to use `developer` role instead.
        # See https://model-spec.openai.com/2025-04-11.html#definitions
        for prompt in prompts:
            if prompt["role"] == "system":
                prompt["role"] = "developer"

        return prompts

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
            "message": repr(message),
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

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: dict) -> dict:
        for round_idx in range(len(test_entry["question"])):
            test_entry["question"][round_idx] = self._substitute_prompt_role(
                test_entry["question"][round_idx]
            )

        inference_data["message"] = []

        return inference_data

    def _compile_tools(self, inference_data: dict, test_entry: dict) -> dict:
        functions: list = test_entry["function"]

        tools = convert_to_tool(functions, GORILLA_TO_OPENAPI, self.model_style)

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

    def add_first_turn_message_FC(
        self, inference_data: dict, first_turn_message: list[dict]
    ) -> dict:
        for message in first_turn_message:
            # @HuanzhiMao fixme, abstract
            if "image_content" in message:
                new_content = []
                for image_content in message["image_content"]:
                    new_content.append(
                        {
                            "type": "input_image",
                            "image_url": f"data:{image_content['type']};base64,{image_content['image_base64']}",
                        }
                    )
                new_content.append({"type": "input_text", "text": message["content"]})
                message["content"] = new_content
                del message["image_content"]
            else:
                message["content"] = [{"type": "input_text", "text": message["content"]}]

        inference_data["message"].extend(first_turn_message)
        return inference_data

    def _add_next_turn_user_message_FC(
        self, inference_data: dict, user_message: list[dict]
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
            if execution_result["result_type"] == ResultType.TEXT:
                tool_message = {
                    "type": "function_call_output",
                    "call_id": tool_call_id,
                    "output": execution_result["result"],
                }
            elif execution_result["result_type"] == ResultType.IMAGE:
                image_content = execution_result["result"]
                tool_message = {
                    "type": "function_call_output",
                    "call_id": tool_call_id,
                    "output": [
                        {
                            "type": "input_image",
                            "image_url": f"data:{image_content['type']};base64,{image_content['image_base64']}",
                        }
                    ],
                }

            inference_data["message"].append(tool_message)

        return inference_data
