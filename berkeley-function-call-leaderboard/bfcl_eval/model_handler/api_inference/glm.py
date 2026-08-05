import os

from bfcl_eval.model_handler.api_inference.openai_completion import OpenAICompletionsHandler
from openai import OpenAI
import httpx
from overrides import override


class GLMAPIHandler(OpenAICompletionsHandler):
    # Zhipu's `input_audio` part exists only for the GLM voice models, none of
    # which are registered here.
    can_handle_audio_input = False
    # The vision models (glm-5v-*) take an `image_url`; the text models do not, which
    # `supports_image_input` decides per model. Zhipu's reference says the `url` field
    # holds "the image URL or Base64 encoding" and their samples show both a bare
    # base64 string and a data URI; the inherited renderer sends the data URI, which is
    # the form Zhipu's own Python SDK uses.
    can_handle_image_input = True
    # Via the inherited workaround -- a GLM tool message content is a string.
    can_handle_image_tool_response = True

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.client = OpenAI(
            api_key=os.getenv("GLM_API_KEY"),
            base_url="https://open.bigmodel.cn/api/paas/v4/",
            timeout=httpx.Timeout(timeout=300.0, connect=8.0),
        )
