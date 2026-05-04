import os
from typing import Any

from bfcl_eval.constants.enums import ResultType
from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from openai import OpenAI
from overrides import override


class KimiHandler(OpenAICompletionsHandler):
    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        is_fc_model,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, is_fc_model, **kwargs)

        self.client = OpenAI(
            base_url="https://api.moonshot.ai/v1",
            # If API Key is from US platform, use the above URL
            # If API Key is from China platform, use the below URL
            # base_url="https://api.moonshot.cn/v1",
            api_key=os.getenv("KIMI_API_KEY")
        )

    @override
    def _query_FC(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        tools = inference_data["tools"]
        inference_data["inference_input_log"] = {"message": repr(message), "tools": tools}

        kwargs = {
            "messages": message,
            "model": self.model_name,
            "temperature": 1,
            "store": False,
        }

        if len(tools) > 0:
            kwargs["tools"] = tools

        return self.generate_with_backoff(**kwargs)

    @override
    def _query_prompting(self, inference_data: dict):
        inference_data["inference_input_log"] = {"message": repr(inference_data["message"])}

        return self.generate_with_backoff(
            messages=inference_data["message"],
            model=self.model_name,
            temperature=1,
            store=False,
        )

    @override
    def _parse_query_response_FC(self, api_response: Any) -> dict:
        response_data = super()._parse_query_response_FC(api_response)

        # Kimi K2.5 thinking mode requires reasoning_content to be echoed back
        # in subsequent assistant tool-call messages; the base handler strips it.
        message = api_response.choices[0].message
        reasoning_content = getattr(message, "reasoning_content", None)
        if reasoning_content:
            response_data["model_responses_message_for_chat_history"][
                "reasoning_content"
            ] = reasoning_content
            response_data["reasoning_content"] = reasoning_content

        return response_data

    @override
    def _add_execution_results_FC(
        self,
        inference_data: dict,
        execution_results: list[dict],
        model_response_data: dict,
    ) -> dict:
        for execution_result, tool_call_id in zip(
            execution_results, model_response_data["tool_call_ids"]
        ):
            if execution_result["result_type"] == ResultType.TEXT:
                tool_message = {
                    "role": "tool",
                    "content": execution_result["result"],
                    "tool_call_id": tool_call_id,
                }
            elif execution_result["result_type"] == ResultType.IMAGE:
                image_content = execution_result["result"]
                tool_message = {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{image_content['type']};base64,{image_content['image_base64']}"
                            },
                        }
                    ],
                }

            inference_data["message"].append(tool_message)

        return inference_data

