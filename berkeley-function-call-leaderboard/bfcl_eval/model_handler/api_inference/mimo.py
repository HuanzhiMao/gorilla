import os

from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from openai import OpenAI


class MiMoHandler(OpenAICompletionsHandler):
    """Xiaomi's MiMo platform, which serves an OpenAI-compatible chat completions API."""

    # The registered model, mimo-v2.5-pro, is text-in. Its omni sibling mimo-v2.5
    # does take images and audio, but through Xiaomi's own part shapes (the audio
    # `data` is a full `data:audio/mpeg;base64,` URI and there is no `format` key),
    # so enabling it here would need an override of `_render_message_content`.
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
            base_url="https://api.xiaomimimo.com/v1",
            api_key=os.getenv("MIMO_API_KEY"),
        )
