import os

from bfcl_eval.model_handler.api_inference.openai_completion import OpenAICompletionsHandler
from openai import OpenAI


class CohereHandler(OpenAICompletionsHandler):
    def __init__(self, model_name, temperature) -> None:
        super().__init__(model_name, temperature)
        self.client = OpenAI(
            api_key=os.getenv("COHERE_API_KEY"),
            base_url="https://api.cohere.ai/compatibility/v1",
        )
        # @HuanzhiMao fixme, only command-a-vision-07-2025 is not FC
        # self.is_fc_model = True

    def _query_prompting(self, inference_data: dict):
        inference_data["inference_input_log"] = {"message": repr(inference_data["message"])}

        return self.generate_with_backoff(
            messages=inference_data["message"],
            model=self.model_name,
            temperature=self.temperature,
            # store=False,
        )