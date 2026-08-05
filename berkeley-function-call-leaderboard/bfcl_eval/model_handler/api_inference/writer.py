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
    # Writer's chat API documents image input and nothing audio-shaped.
    can_handle_audio_input = False
    # `image_url` is an object holding only `url` -- which is what the inherited
    # renderer emits, since it never sets `detail`.
    can_handle_image_input = True
    # Undocumented for tool messages, so the inherited workaround is used; it relies
    # only on features Writer does document.
    can_handle_image_tool_response = True

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_style = ModelStyle.WRITER
        self.client = Writer(api_key=os.getenv("WRITER_API_KEY"))

    @retry_with_backoff(error_type=RateLimitError)
    @override
    def generate_with_backoff(self, **kwargs):
        start_time = time.time()
        api_response = self.client.chat.chat(**kwargs)
        end_time = time.time()

        return api_response, end_time - start_time
