import os
import time

from bfcl_eval.constants.enums import ModelStyle
from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from bfcl_eval.model_handler.utils import retry_with_backoff
from openai import RateLimitError
from overrides import override
from writerai import Writer


class WriterHandler(OpenAICompletionsHandler):
    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        is_fc_model,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, is_fc_model, **kwargs)
        self.model_style = ModelStyle.WRITER
        self.client = Writer(api_key=os.getenv("WRITER_API_KEY"))

    @retry_with_backoff(error_type=RateLimitError)
    @override
    def generate_with_backoff(self, **kwargs):
        start_time = time.time()
        api_response = self.client.chat.chat(**kwargs)
        end_time = time.time()

        return api_response, end_time - start_time
