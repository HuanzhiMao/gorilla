import os
import time
from typing import Any

from bfcl_eval.constants.type_mappings import GORILLA_TO_OPENAPI
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.constants.enums import ModelStyle
from bfcl_eval.model_handler.utils import (
    convert_to_tool,
    default_decode_ast_prompting,
    default_decode_execute_prompting,
    extract_system_prompt,
    format_execution_results_prompting,
    retry_with_backoff,
    system_prompt_pre_processing_chat_model,
    convert_system_prompt_into_user_prompt,
    combine_consecutive_user_prompts,
)
from google import genai
from google.genai.types import (
    AutomaticFunctionCallingConfig,
    Content,
    GenerateContentConfig,
    Part,
    ThinkingConfig,
    Tool,
)


class GemmaAPIHandler(BaseHandler):
    def __init__(self, model_name, temperature) -> None:
        super().__init__(model_name, temperature)
        self.model_style = ModelStyle.GOOGLE
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GOOGLE_API_KEY environment variable must be set for Gemini models"
            )
        self.client = genai.Client(api_key=api_key)

    @staticmethod
    def _substitute_prompt_role(prompts: list[dict]) -> list[dict]:
        # Allowed roles: user, model
        for prompt in prompts:
            if prompt["role"] == "user":
                prompt["role"] = "user"
            elif prompt["role"] == "assistant":
                prompt["role"] = "model"

        return prompts

    def decode_ast(self, result, language, has_tool_call_tag):
        if "FC" not in self.model_name:
            result = result.replace("```tool_code\n", "").replace("\n```", "")
            return default_decode_ast_prompting(result, language, has_tool_call_tag)
        else:
            if type(result) is not list:
                result = [result]
            return result

    def decode_execute(self, result, has_tool_call_tag):
        if "FC" not in self.model_name:
            result = result.replace("```tool_code\n", "").replace("\n```", "")
            return default_decode_execute_prompting(result, has_tool_call_tag)
        else:
            func_call_list = []
            for function_call in result:
                for func_name, func_args in function_call.items():
                    func_call_list.append(
                        f"{func_name}({','.join([f'{k}={repr(v)}' for k, v in func_args.items()])})"
                    )
            return func_call_list

    # We can't retry on ClientError because it's too broad.
    # Both rate limit and invalid function description will trigger google.genai.errors.ClientError
    @retry_with_backoff(error_message_pattern=r".*RESOURCE_EXHAUSTED.*")
    def generate_with_backoff(self, **kwargs):
        start_time = time.time()
        api_response = self.client.models.generate_content(**kwargs)
        end_time = time.time()

        return api_response, end_time - start_time


    #### Prompting methods ####

    def _query_prompting(self, inference_data: dict):
        inference_data["inference_input_log"] = {
            "message": repr(inference_data["message"]),
            "system_prompt": inference_data.get("system_prompt", None),
        }

        config = GenerateContentConfig(
            temperature=self.temperature,
        )

        api_response = self.generate_with_backoff(
            model=self.model_name.replace("-FC", ""),
            contents=inference_data["message"],
            config=config,
        )
        return api_response

    def _pre_query_processing_prompting(self, test_entry: dict) -> dict:
        functions: list = test_entry["function"]
        test_entry_id: str = test_entry["id"]

        for round_idx in range(len(test_entry["question"])):
            test_entry["question"][round_idx] = self._substitute_prompt_role(
                test_entry["question"][round_idx]
            )

        test_entry["question"][0] = system_prompt_pre_processing_chat_model(
            test_entry["question"][0], functions, test_entry_id
        )
        
        # Gemma doesn't take system prompt
        for round_idx in range(len(test_entry["question"])):
            test_entry["question"][round_idx] = convert_system_prompt_into_user_prompt(
                test_entry["question"][round_idx]
            )
            test_entry["question"][round_idx] = combine_consecutive_user_prompts(
                test_entry["question"][round_idx]
            )
        
        return {"message": []}

    def _parse_query_response_prompting(self, api_response: Any) -> dict:
        if (
            len(api_response.candidates) > 0
            and api_response.candidates[0].content
            and api_response.candidates[0].content.parts
            and len(api_response.candidates[0].content.parts) > 0
        ):
            # @HuanzhiMao fixme, gemma doesn't have reasoning
            # also, merge with the existing pr
            assert (
                len(api_response.candidates[0].content.parts) <= 2
            ), f"Length of response parts should be less than or equal to 2. {api_response.candidates[0].content.parts}"

            model_responses = ""
            reasoning_content = ""
            for part in api_response.candidates[0].content.parts:
                if part.thought:
                    reasoning_content = part.text
                else:
                    model_responses = part.text

        else:
            model_responses = "The model did not return any response."
            reasoning_content = ""

        return {
            "model_responses": model_responses,
            "reasoning_content": reasoning_content,
            "input_token": api_response.usage_metadata.prompt_token_count,
            "output_token": api_response.usage_metadata.candidates_token_count,
        }

    def add_first_turn_message_prompting(
        self, inference_data: dict, first_turn_message: list[dict]
    ) -> dict:
        for message in first_turn_message:
            if "image_content" in message:
                image_content = message["image_content"]
                parts = [
                    Part.from_bytes(data=image_content["image_bytes"], mime_type=image_content["type"]),
                    Part(text=message["content"])
                ]
            else:
                parts = [Part(text=message["content"])]
                
            inference_data["message"].append(
                Content(
                    role=message["role"],
                    parts=parts,
                )
            )
        return inference_data

    def _add_next_turn_user_message_prompting(
        self, inference_data: dict, user_message: list[dict]
    ) -> dict:
        return self.add_first_turn_message_prompting(inference_data, user_message)

    def _add_assistant_message_prompting(
        self, inference_data: dict, model_response_data: dict
    ) -> dict:
        inference_data["message"].append(
            Content(
                role="model",
                parts=[
                    Part(text=model_response_data["model_responses"]),
                ],
            )
        )
        return inference_data

    def _add_execution_results_prompting(
        self, inference_data: dict, execution_results: list[str], model_response_data: dict
    ) -> dict:
        formatted_results_message = format_execution_results_prompting(
            inference_data, execution_results, model_response_data
        )
        tool_message = Content(
            role="user",
            parts=[
                Part(text=formatted_results_message),
            ],
        )
        inference_data["message"].append(tool_message)
        return inference_data
