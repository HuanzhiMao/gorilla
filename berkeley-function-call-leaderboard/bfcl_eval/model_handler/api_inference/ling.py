import os

from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from openai import OpenAI


class LingAPIHandler(OpenAICompletionsHandler):
    """Ant Group's Bailing/Tbox platform, which serves an OpenAI-compatible API.

    An earlier version of this handler drove Ling-lite-1.5 in prompting mode and mapped
    each registry key onto a dated API name (`Ling-lite-1.5-250604`). The prompting
    pathway is gone, so the FC methods inherited from OpenAICompletionsHandler are all
    that is left, and `model_name` is sent to the API as-is.
    """

    # Bailing/Tbox documents message content as a plain string -- text only.
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
        self.client = OpenAI(
            base_url="https://api.tbox.cn/api/llm/v1/",
            api_key=os.getenv("LING_API_KEY"),
        )
