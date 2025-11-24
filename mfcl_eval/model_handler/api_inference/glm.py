import os

from mfcl_eval.model_handler.api_inference.openai_completion import OpenAICompletionsHandler
from openai import OpenAI
<<<<<<< HEAD
from mfcl_eval.model_handler.utils import default_decode_execute_prompting
=======
from overrides import override
from typing import Any
import httpx

>>>>>>> audio

class GLMAPIHandler(OpenAICompletionsHandler):
    def __init__(self, model_name, temperature) -> None:
        super().__init__(model_name, temperature)
        self.client = OpenAI(
            api_key=os.getenv("GLM_API_KEY"),
<<<<<<< HEAD
            base_url="https://open.bigmodel.cn/api/paas/v4",
            # timeout=httpx.Timeout(timeout=300.0, connect=8.0)
        )
        # @HuanzhiMao fixme, only glm-4.5v is not FC
        # self.is_fc_model = True

    def _query_prompting(self, inference_data: dict):
        inference_data["inference_input_log"] = {"message": repr(inference_data["message"])}
        # print(inference_data["message"])

        return self.generate_with_backoff(
            messages=inference_data["message"],
            model=self.model_name,
            extra_body={
                "thinking": {
                    "type": "enabled",
                },
            },
            temperature=0.01,
            # store=False,
        )
        
    def _parse_query_response_prompting(self, api_response) -> dict:
        
        model_response = api_response.choices[0].message.content
        if "<|begin_of_box|>" in model_response:
            thinking_content = model_response.split("<|begin_of_box|>")[0]
            model_response = model_response.split("<|begin_of_box|>")[1].split("<|end_of_box|>")[0]
        else:
            thinking_content = ""
        return {
            "model_responses": model_response,
            "model_responses_message_for_chat_history": api_response.choices[0].message,
            "reasoning_content": thinking_content,
            "input_token": api_response.usage.prompt_tokens,
            "output_token": api_response.usage.completion_tokens,
        }
    def decode_execute(self, result, has_tool_call_tag):
        # result = result.replace("<|begin_of_box|>", "").replace("<|end_of_box|>", "")
        return default_decode_execute_prompting(result)
=======
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            timeout=httpx.Timeout(timeout=300.0, connect=8.0)
        )
        self.is_fc_model = True
>>>>>>> audio
