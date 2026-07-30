from dataclasses import dataclass, field
from re import S
from typing import Optional

from bfcl_eval.model_handler.api_inference.claude import ClaudeHandler
from bfcl_eval.model_handler.api_inference.deepseek import DeepSeekAPIHandler
from bfcl_eval.model_handler.api_inference.gemini import GeminiHandler
from bfcl_eval.model_handler.api_inference.glm import GLMAPIHandler
from bfcl_eval.model_handler.api_inference.gorilla import GorillaHandler
from bfcl_eval.model_handler.api_inference.grok import GrokHandler
from bfcl_eval.model_handler.api_inference.kimi import KimiHandler
from bfcl_eval.model_handler.api_inference.meta import MetaHandler
from bfcl_eval.model_handler.api_inference.mining import MiningHandler
from bfcl_eval.model_handler.api_inference.mistral import MistralHandler
from bfcl_eval.model_handler.api_inference.nanbeige import NanbeigeAPIHandler
from bfcl_eval.model_handler.api_inference.nova import NovaHandler
from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from bfcl_eval.model_handler.api_inference.openai_response import OpenAIResponsesHandler
from bfcl_eval.model_handler.api_inference.qwen import (
    QwenAgentNoThinkHandler,
    QwenAgentThinkHandler,
    QwenAPIHandler,
)
from bfcl_eval.model_handler.api_inference.writer import WriterHandler
from bfcl_eval.model_handler.local_inference.base_oss_handler import OSSHandler


# -----------------------------------------------------------------------------
# A mapping of model identifiers to their respective model configurations.
# Each key corresponds to the model id passed to the `--model` argument
# in both generation and evaluation commands.
# Make sure to update the `supported_models.py` file as well when updating this map.
#
# Which map does a new model go in?
#   1. If its weights are public, self-host it (`local_inference_model_map`) rather
#      than calling the vendor API, so the score reflects the model and not a
#      provider's serving stack.
#   2. Except above ~500B total parameters, where self-hosting stops being
#      reproducible for most people -- those go through the API
#      (`api_inference_model_map`) even when the weights are public.
#   3. A model with no public weights, or whose tool-call parser is missing from
#      every released vLLM, has to use the API regardless of size.
# No model should appear in both maps.
# -----------------------------------------------------------------------------


@dataclass
class ModelConfig:
    # @HuanzhiMao FIXME: We should let the tool compilation step also take this into account, underscore_to_dot
    """
    Model configuration class for storing model metadata and settings.

    Attributes:
        model_name (str): Name of the model as used in the vendor API or on Hugging Face (may not be unique).
        display_name (str): Model name as it should appear on the leaderboard.
        url (str): Reference URL for the model or hosting service.
        org (str): Organization providing the model.
        license (str): License under which the model is released.
        model_handler (str): Handler name for invoking the model.
        input_price (Optional[float]): USD per million input tokens (None for open source models).
        output_price (Optional[float]): USD per million output tokens (None for open source models).
        underscore_to_dot (bool): True if model does not support '.' in function names, in which case we will replace '.' with '_'. Currently this only matters for checker.
        supports_audio_input (bool): True if the model supports native audio input. Required for true audio tasks.
        supports_image_input (bool): True if the model supports vision/image input. Required for vision tasks.
        is_reasoning_model (bool): True if the model is a reasoning model and we are using its reasoning mode.

    """

    model_name: str
    display_name: str
    url: str
    org: str
    license: str

    model_handler: str

    # Prices are in USD per million tokens; open source models have None
    input_price: Optional[float] = None
    output_price: Optional[float] = None

    # True if this model does not allow '.' in function names
    underscore_to_dot: bool = False

    # True if the model supports native audio input. Required for true audio tasks.
    supports_audio_input: bool = False

    # True if the model supports vision/image input. Required for vision tasks.
    supports_image_input: bool = False

    # True if the model is a reasoning model and we are using its reasoning mode.
    is_reasoning_model: bool = False


@dataclass
class OSSModelConfig(ModelConfig):
    """
    OSS model configuration, carrying additional vLLM-specific settings.
    Attributes:
        vllm_tool_call_parser: The tool call parser to use for the model.
        vllm_reasoning_parser: The reasoning parser to use for the model.
        vllm_extra_serve_args: Extra serve arguments to pass to the vllm engine.
        inference_request_extra_body: Per-request fields merged into the OpenAI
            client's ``extra_body`` at inference time (e.g.
            ``{"chat_template_kwargs": {"thinking": True}}``).

    Note: input_price and output_price are not used for OSS models, as they will be set to None by default.
    """

    vllm_tool_call_parser: Optional[str] = None
    vllm_reasoning_parser: Optional[str] = None
    vllm_extra_serve_args: list[str] = field(default_factory=list)
    inference_request_extra_body: dict = field(default_factory=dict)


# Inference through API calls
api_inference_model_map = {
    # "gorilla-openfunctions-v2": ModelConfig(
    #     model_name="gorilla-openfunctions-v2",
    #     display_name="Gorilla-OpenFunctions-v2",
    #     url="https://gorilla.cs.berkeley.edu/blogs/7_open_functions_v2.html",
    #     org="Gorilla LLM",
    #     license="Apache 2.0",
    #     model_handler=GorillaHandler,
    #     input_price=None,
    #     output_price=None,
    #     underscore_to_dot=False,
    # ),
    # DeepSeek-V4-Pro has MIT weights on HF, but at 1.6T parameters it is far past the
    # point where self-hosting is reproducible, so it is API-only.
    "DeepSeek-V4-Pro": ModelConfig(
        model_name="deepseek-v4-pro",
        display_name="DeepSeek-V4-Pro",
        url="https://api-docs.deepseek.com/news/news260424",
        org="DeepSeek",
        license="MIT",
        model_handler=DeepSeekAPIHandler,
        input_price=None,
        output_price=None,
        underscore_to_dot=True,
    ),
    "DeepSeek-V4-Flash": ModelConfig(
        model_name="deepseek-v4-flash",
        display_name="DeepSeek-V4-Flash",
        url="https://api-docs.deepseek.com/news/news260424",
        org="DeepSeek",
        license="MIT",
        model_handler=DeepSeekAPIHandler,
        input_price=None,
        output_price=None,
        underscore_to_dot=True,
    ),
    "gpt-5.6-sol": ModelConfig(
        model_name="gpt-5.6-sol",
        display_name="GPT-5.6-Sol",
        url="https://openai.com/index/gpt-5-6/",
        org="OpenAI",
        license="Proprietary",
        model_handler=OpenAIResponsesHandler,
        input_price=5,
        output_price=30,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    "gpt-5.6-terra": ModelConfig(
        model_name="gpt-5.6-terra",
        display_name="GPT-5.6-Terra",
        url="https://openai.com/index/gpt-5-6/",
        org="OpenAI",
        license="Proprietary",
        model_handler=OpenAIResponsesHandler,
        input_price=2.5,
        output_price=15,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    "gpt-5.6-luna": ModelConfig(
        model_name="gpt-5.6-luna",
        display_name="GPT-5.6-Luna",
        url="https://openai.com/index/gpt-5-6/",
        org="OpenAI",
        license="Proprietary",
        model_handler=OpenAIResponsesHandler,
        input_price=1,
        output_price=6,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    "claude-opus-5": ModelConfig(
        model_name="claude-opus-5",
        display_name="Claude-Opus-5",
        url="https://www.anthropic.com/news/claude-opus-5",
        org="Anthropic",
        license="Proprietary",
        model_handler=ClaudeHandler,
        input_price=5,
        output_price=25,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    "claude-sonnet-5": ModelConfig(
        model_name="claude-sonnet-5",
        display_name="Claude-Sonnet-5",
        url="https://www.anthropic.com/news/claude-sonnet-5",
        org="Anthropic",
        license="Proprietary",
        model_handler=ClaudeHandler,
        input_price=3,
        output_price=15,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    "claude-haiku-4-5-20251001": ModelConfig(
        model_name="claude-haiku-4-5-20251001",
        display_name="Claude-Haiku-4-5-20251001",
        url="https://www.anthropic.com/news/claude-haiku-4-5",
        org="Anthropic",
        license="Proprietary",
        model_handler=ClaudeHandler,
        input_price=1,
        output_price=5,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    # Muse Spark is Meta Superintelligence Labs' successor to Llama, and unlike Llama
    # it is API-only (no open weights). It exposes reasoning effort (minimal..xhigh)
    # on a single model string; we run it at Meta's default effort.
    # Inputs are text/image/video/PDF -- no audio.
    "muse-spark-1.1": ModelConfig(
        model_name="muse-spark-1.1",
        display_name="Muse-Spark-1.1",
        url="https://ai.meta.com/blog/introducing-muse-spark-meta-model-api/",
        org="Meta",
        license="Proprietary",
        model_handler=MetaHandler,
        input_price=1.25,
        output_price=4.25,
        underscore_to_dot=True,
        supports_image_input=True,
        is_reasoning_model=True,
    ),
    # @HuanzhiMao TODO: update to Nova Pro 2 when it's out
    # Nova series don't support audio input
    "nova-pro-v1.0": ModelConfig(
        model_name="us.amazon.nova-pro-v1:0",
        display_name="Amazon-Nova-Pro-v1:0",
        url="https://aws.amazon.com/cn/ai/generative-ai/nova/",
        org="Amazon",
        license="Proprietary",
        model_handler=NovaHandler,
        input_price=0.8,
        output_price=3.2,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    "nova-2-lite-v1.0": ModelConfig(
        model_name="us.amazon.nova-2-lite-v1:0",
        display_name="Amazon-Nova-2-Lite-v1:0",
        url="https://aws.amazon.com/cn/ai/generative-ai/nova/",
        org="Amazon",
        license="Proprietary",
        model_handler=NovaHandler,
        input_price=0.3,
        output_price=2.5,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    "nova-micro-v1.0": ModelConfig(
        model_name="us.amazon.nova-micro-v1:0",
        display_name="Amazon-Nova-Micro-v1:0",
        url="https://aws.amazon.com/cn/ai/generative-ai/nova/",
        org="Amazon",
        license="Proprietary",
        model_handler=NovaHandler,
        input_price=0.035,
        output_price=0.14,
        underscore_to_dot=True,
    ),
    # Mistral Large 3 is Apache 2.0 and self-hostable in principle, but at 675B total
    # parameters (41B active) it is over the self-hosting cutoff, so we call the API.
    # `mistral-large-2512` is the pinned id for the 25.12 release; `mistral-large-latest`
    # is the moving alias, which we avoid so runs stay comparable.
    "mistral-large-2512": ModelConfig(
        model_name="mistral-large-2512",
        display_name="Mistral-Large-3",
        url="https://docs.mistral.ai/models/model-cards/mistral-large-3-25-12",
        org="Mistral AI",
        license="apache-2.0",
        model_handler=MistralHandler,
        input_price=0.5,
        output_price=1.5,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    "gemini-3.1-flash-lite-preview": ModelConfig(
        model_name="gemini-3.1-flash-lite-preview",
        display_name="Gemini-3.1-Flash-Lite-Preview",
        url="https://deepmind.google/technologies/gemini/flash-lite/",
        org="Google",
        license="Proprietary",
        model_handler=GeminiHandler,
        underscore_to_dot=True,
    ),
    "gemini-3.5-flash": ModelConfig(
        model_name="gemini-3.5-flash",
        display_name="Gemini-3.5-Flash",
        url="https://deepmind.google/technologies/gemini/flash/",
        org="Google",
        license="Proprietary",
        model_handler=GeminiHandler,
        input_price=0.5,
        output_price=3,
        underscore_to_dot=True,
    ),
    "gemini-3.1-pro-preview": ModelConfig(
        model_name="gemini-3.1-pro-preview",
        display_name="Gemini-3.1-Pro-Preview",
        url="https://deepmind.google/technologies/gemini/pro/",
        org="Google",
        license="Proprietary",
        model_handler=GeminiHandler,
        input_price=2,
        output_price=12,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    # @HuanzhiMao FIXME: check if this is still available
    "palmyra-x5": ModelConfig(
        model_name="palmyra-x5",
        display_name="palmyra-x5",
        url="https://dev.writer.com/home/models#palmyra-x5",
        org="Writer",
        license="Proprietary",
        model_handler=WriterHandler,
        underscore_to_dot=True,
    ),
    # Grok 4.5 exposes reasoning effort (low/medium/high) on a single model string;
    # we run it at xAI's default effort (high).
    "grok-4.5": ModelConfig(
        model_name="grok-4.5",
        display_name="Grok-4.5",
        url="https://docs.x.ai/docs/models",
        org="xAI",
        license="Proprietary",
        model_handler=GrokHandler,
        input_price=2,
        output_price=6,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    # GLM-5.2's weights are MIT, but at 753B parameters (~1.5TB in bf16) it is over the
    # self-hosting cutoff, so we evaluate it through the Z.ai API. Z.ai serves it in
    # thinking mode by default, matching the mode the display name advertises.
    "glm-5.2": ModelConfig(
        model_name="glm-5.2",
        display_name="GLM-5.2 (thinking)",
        url="https://huggingface.co/zai-org/GLM-5.2",
        org="Zhipu AI",
        license="MIT",
        model_handler=GLMAPIHandler,
        input_price=None,
        output_price=None,
        underscore_to_dot=True,
        is_reasoning_model=True,
    ),
    "glm-5v-turbo": ModelConfig(
        model_name="glm-5v-turbo",
        display_name="GLM-5v-Turbo",
        url="https://docs.z.ai/guides/vlm/glm-5v-turbo",
        org="Zhipu AI",
        license="proprietary",
        model_handler=GLMAPIHandler,
        input_price=0.3,
        output_price=2.23,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    # Kimi-K3 has open weights (moonshotai/Kimi-K3, modified MIT) but stays on the
    # Moonshot API on both counts: it is 2.8T parameters, and vLLM's `kimi_k3` parsers
    # are only on `main`, in none of the releases (checked v0.23.0 through v0.26.0).
    "kimi-k3": ModelConfig(
        model_name="kimi-k3",
        display_name="Kimi-K3",
        url="https://huggingface.co/moonshotai/Kimi-K3",
        org="MoonshotAI",
        license="modified-mit",
        model_handler=KimiHandler,
        input_price=None,
        output_price=None,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    "Nanbeige3.5-Pro-Thinking": ModelConfig(
        model_name="Nanbeige3.5-Pro-Thinking",
        display_name="Nanbeige3.5-Pro-Thinking",
        url="https://huggingface.co/Nanbeige",
        org="Nanbeige",
        license="apache-2.0",
        model_handler=NanbeigeAPIHandler,
        input_price=None,
        output_price=None,
        underscore_to_dot=True,
    ),
}

# Inference through local hosting
local_inference_model_map = {
    # @huanzhiMao FIXME, check, for oss model, if is_fc_model, do we still supply system prompt?
    "google/gemma-4-E2B-it": OSSModelConfig(
        model_name="google/gemma-4-E2B-it",
        display_name="Gemma-4-E2B-it",
        url="https://huggingface.co/google/gemma-4-E2B-it",
        org="Google",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        vllm_tool_call_parser="gemma4",
        vllm_reasoning_parser="gemma4",
        inference_request_extra_body={"chat_template_kwargs": {"enable_thinking": True}},
        supports_audio_input=True,
        supports_image_input=True,
    ),
    "google/gemma-4-E4B-it": OSSModelConfig(
        model_name="google/gemma-4-E4B-it",
        display_name="Gemma-4-E4B-it",
        url="https://huggingface.co/google/gemma-4-E4B-it",
        org="Google",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        vllm_tool_call_parser="gemma4",
        vllm_reasoning_parser="gemma4",
        inference_request_extra_body={"chat_template_kwargs": {"enable_thinking": True}},
        supports_audio_input=True,
        supports_image_input=True,
    ),
    "google/gemma-4-26B-A4B-it": OSSModelConfig(
        model_name="google/gemma-4-26B-A4B-it",
        display_name="Gemma-4-26B-A4B-it",
        url="https://huggingface.co/google/gemma-4-26B-A4B-it",
        org="Google",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        vllm_tool_call_parser="gemma4",
        vllm_reasoning_parser="gemma4",
        inference_request_extra_body={"chat_template_kwargs": {"enable_thinking": True}},
        supports_image_input=True,
    ),
    "google/gemma-4-31B-it": OSSModelConfig(
        model_name="google/gemma-4-31B-it",
        display_name="Gemma-4-31B-it",
        url="https://huggingface.co/google/gemma-4-31B-it",
        org="Google",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        vllm_tool_call_parser="gemma4",
        vllm_reasoning_parser="gemma4",
        inference_request_extra_body={"chat_template_kwargs": {"enable_thinking": True}},
        supports_image_input=True,
    ),
    # @HuanzhiMao FIXME: Check below for is_reasoning_model
    "google/functiongemma-270m-it": OSSModelConfig(
        model_name="google/functiongemma-270m-it",
        display_name="FunctionGemma-270m-it",
        url="https://ai.google.dev/gemma/docs/functiongemma",
        org="Google",
        license="gemma-terms-of-use",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="functiongemma",
    ),
    "meta-llama/Llama-4-Scout-17B-16E-Instruct": OSSModelConfig(
        model_name="meta-llama/Llama-4-Scout-17B-16E-Instruct",
        display_name="Llama-4-Scout-17B-16E-Instruct",
        url="https://huggingface.co/meta-llama/Llama-4-Scout-17B-16E-Instruct",
        org="Meta",
        license="Meta Llama 4 Community",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        supports_image_input=True,
        vllm_tool_call_parser="llama4_pythonic",
    ),
    "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8": OSSModelConfig(
        model_name="meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        display_name="Llama-4-Maverick-17B-128E-Instruct-FP8",
        url="https://huggingface.co/meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
        org="Meta",
        license="Meta Llama 4 Community",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        supports_image_input=True,
        vllm_tool_call_parser="llama4_pythonic",
    ),
    "Salesforce/Llama-xLAM-2-70b-fc-r": OSSModelConfig(
        model_name="Salesforce/Llama-xLAM-2-70b-fc-r",
        display_name="xLAM-2-70b-fc-r",
        url="https://huggingface.co/Salesforce/Llama-xLAM-2-70b-fc-r",
        org="Salesforce",
        license="cc-by-nc-4.0",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="xlam",
    ),
    "Salesforce/Llama-xLAM-2-8b-fc-r": OSSModelConfig(
        model_name="Salesforce/Llama-xLAM-2-8b-fc-r",
        display_name="xLAM-2-8b-fc-r",
        url="https://huggingface.co/Salesforce/Llama-xLAM-2-8b-fc-r",
        org="Salesforce",
        license="cc-by-nc-4.0",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="xlam",
    ),
    "Salesforce/xLAM-2-32b-fc-r": OSSModelConfig(
        model_name="Salesforce/xLAM-2-32b-fc-r",
        display_name="xLAM-2-32b-fc-r",
        url="https://huggingface.co/Salesforce/xLAM-2-32b-fc-r",
        org="Salesforce",
        license="cc-by-nc-4.0",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="xlam",
    ),
    "Salesforce/xLAM-2-3b-fc-r": OSSModelConfig(
        model_name="Salesforce/xLAM-2-3b-fc-r",
        display_name="xLAM-2-3b-fc-r",
        url="https://huggingface.co/Salesforce/xLAM-2-3b-fc-r",
        org="Salesforce",
        license="cc-by-nc-4.0",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="xlam",
    ),
    "Salesforce/xLAM-2-1b-fc-r": OSSModelConfig(
        model_name="Salesforce/xLAM-2-1b-fc-r",
        display_name="xLAM-2-1b-fc-r",
        url="https://huggingface.co/Salesforce/xLAM-2-1b-fc-r",
        org="Salesforce",
        license="cc-by-nc-4.0",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="xlam",
    ),
    # Mistral Medium 3.5 ships open weights (Modified MIT), so we self-host it
    # instead of going through the Mistral API.
    # Hybrid reasoning: the chat template accepts only `reasoning_effort` of 'none'
    # or 'high' and defaults to 'none'; we serve it in reasoning mode, which Mistral
    # recommends for agentic use. vLLM forwards the top-level `reasoning_effort`
    # request field straight into the chat template.
    "mistralai/Mistral-Medium-3.5-128B": OSSModelConfig(
        model_name="mistralai/Mistral-Medium-3.5-128B",
        display_name="Mistral-Medium-3.5-128B",
        url="https://huggingface.co/mistralai/Mistral-Medium-3.5-128B",
        org="Mistral AI",
        license="Modified MIT",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        supports_image_input=True,
        vllm_tool_call_parser="mistral",
        vllm_reasoning_parser="mistral",
        inference_request_extra_body={"reasoning_effort": "high"},
    ),
    # @HuanzhiMao FIXME: Double check this
    "mistralai/Mistral-Small-4-119B-2603": OSSModelConfig(
        model_name="mistralai/Mistral-Small-4-119B-2603",
        display_name="Mistral-Small-4-119B-2603",
        url="https://huggingface.co/mistralai/Mistral-Small-4-119B-2603",
        org="Mistral AI",
        license="Proprietary",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        supports_image_input=True,
        vllm_tool_call_parser="mistral",
    ),
    # FIXME, check
    "microsoft/Phi-4-mini-instruct": OSSModelConfig(
        model_name="microsoft/Phi-4-mini-instruct",
        display_name="Phi-4-mini-instruct",
        url="https://huggingface.co/microsoft/Phi-4-mini-instruct",
        org="Microsoft",
        license="MIT",
        model_handler=OSSHandler,
        vllm_tool_call_parser="phi4_mini_json",
        underscore_to_dot=False,
    ),
    "ibm-granite/granite-3.2-8b-instruct": OSSModelConfig(
        model_name="ibm-granite/granite-3.2-8b-instruct",
        display_name="Granite-3.2-8B-Instruct",
        url="https://huggingface.co/ibm-granite/granite-3.2-8b-instruct",
        org="IBM",
        license="Apache-2.0",
        model_handler=OSSHandler,
        vllm_tool_call_parser="granite",
        underscore_to_dot=False,
    ),
    "ibm-granite/granite-3.1-8b-instruct": OSSModelConfig(
        model_name="ibm-granite/granite-3.1-8b-instruct",
        display_name="Granite-3.1-8B-Instruct",
        url="https://huggingface.co/ibm-granite/granite-3.1-8b-instruct",
        org="IBM",
        license="Apache-2.0",
        model_handler=OSSHandler,
        vllm_tool_call_parser="granite",
        underscore_to_dot=False,
    ),
    "ibm-granite/granite-4.0-350m": OSSModelConfig(
        model_name="ibm-granite/granite-4.0-350m",
        display_name="Granite-4.0-350m",
        url="https://huggingface.co/ibm-granite/granite-4.0-350m",
        org="IBM",
        license="Apache-2.0",
        model_handler=OSSHandler,
        vllm_tool_call_parser="granite4",
        underscore_to_dot=False,
    ),
    "MadeAgents/Hammer2.1-7b": OSSModelConfig(
        model_name="MadeAgents/Hammer2.1-7b",
        display_name="Hammer2.1-7b",
        url="https://huggingface.co/MadeAgents/Hammer2.1-7b",
        org="MadeAgents",
        license="cc-by-nc-4.0",
        model_handler=OSSHandler,
        vllm_tool_call_parser="xlam",
        underscore_to_dot=False,
    ),
    "MadeAgents/Hammer2.1-3b": OSSModelConfig(
        model_name="MadeAgents/Hammer2.1-3b",
        display_name="Hammer2.1-3b",
        url="https://huggingface.co/MadeAgents/Hammer2.1-3b",
        org="MadeAgents",
        license="qwen-research",
        model_handler=OSSHandler,
        vllm_tool_call_parser="xlam",
        underscore_to_dot=False,
    ),
    "MadeAgents/Hammer2.1-1.5b": OSSModelConfig(
        model_name="MadeAgents/Hammer2.1-1.5b",
        display_name="Hammer2.1-1.5b",
        url="https://huggingface.co/MadeAgents/Hammer2.1-1.5b",
        org="MadeAgents",
        license="cc-by-nc-4.0",
        model_handler=OSSHandler,
        vllm_tool_call_parser="xlam",
        underscore_to_dot=False,
    ),
    "MadeAgents/Hammer2.1-0.5b": OSSModelConfig(
        model_name="MadeAgents/Hammer2.1-0.5b",
        display_name="Hammer2.1-0.5b",
        url="https://huggingface.co/MadeAgents/Hammer2.1-0.5b",
        org="MadeAgents",
        license="cc-by-nc-4.0",
        model_handler=OSSHandler,
        vllm_tool_call_parser="xlam",
        underscore_to_dot=False,
    ),
    "Qwen/Qwen3.5-0.8B": OSSModelConfig(
        model_name="Qwen/Qwen3.5-0.8B",
        display_name="Qwen3.5-0.8B",
        url="https://huggingface.co/Qwen/Qwen3.5-0.8B",
        org="Qwen",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=True,
        vllm_reasoning_parser="qwen3",
        vllm_tool_call_parser="qwen3_coder",
        supports_image_input=True,
    ),
    "Qwen/Qwen3.5-2B": OSSModelConfig(
        model_name="Qwen/Qwen3.5-2B",
        display_name="Qwen3.5-2B",
        url="https://huggingface.co/Qwen/Qwen3.5-2B",
        org="Qwen",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=True,
        vllm_reasoning_parser="qwen3",
        vllm_tool_call_parser="qwen3_coder",
        supports_image_input=True,
    ),
    "Qwen/Qwen3.5-4B": OSSModelConfig(
        model_name="Qwen/Qwen3.5-4B",
        display_name="Qwen3.5-4B",
        url="https://huggingface.co/Qwen/Qwen3.5-4B",
        org="Qwen",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=True,
        vllm_reasoning_parser="qwen3",
        vllm_tool_call_parser="qwen3_coder",
        supports_image_input=True,
    ),
    "Qwen/Qwen3.5-9B": OSSModelConfig(
        model_name="Qwen/Qwen3.5-9B",
        display_name="Qwen3.5-9B",
        url="https://huggingface.co/Qwen/Qwen3.5-9B",
        org="Qwen",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=True,
        vllm_reasoning_parser="qwen3",
        vllm_tool_call_parser="qwen3_coder",
        supports_image_input=True,
    ),
    "Qwen/Qwen3.6-27B": OSSModelConfig(
        model_name="Qwen/Qwen3.6-27B",
        display_name="Qwen3.6-27B",
        url="https://huggingface.co/Qwen/Qwen3.6-27B",
        org="Qwen",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=True,
        vllm_reasoning_parser="qwen3",
        vllm_tool_call_parser="qwen3_coder",
        supports_image_input=True,
    ),
    "Qwen/Qwen3.6-35B-A3B": OSSModelConfig(
        model_name="Qwen/Qwen3.6-35B-A3B",
        display_name="Qwen3.6-35B-A3B",
        url="https://huggingface.co/Qwen/Qwen3.6-35B-A3B",
        org="Qwen",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=True,
        vllm_reasoning_parser="qwen3",
        vllm_tool_call_parser="qwen3_coder",
        supports_image_input=True,
    ),
    "Qwen/Qwen3.5-122B-A10B": OSSModelConfig(
        model_name="Qwen/Qwen3.5-122B-A10B",
        display_name="Qwen3.5-122B-A10B",
        url="https://huggingface.co/Qwen/Qwen3.5-122B-A10B",
        org="Qwen",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=True,
        vllm_reasoning_parser="qwen3",
        vllm_tool_call_parser="qwen3_coder",
        supports_image_input=True,
    ),
    "Qwen/Qwen3.5-397B-A17B": OSSModelConfig(
        model_name="Qwen/Qwen3.5-397B-A17B",
        display_name="Qwen3.5-397B-A17B",
        url="https://huggingface.co/Qwen/Qwen3.5-397B-A17B",
        org="Qwen",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=True,
        vllm_reasoning_parser="qwen3",
        vllm_tool_call_parser="qwen3_coder",
        supports_image_input=True,
    ),
    # Command A+ replaces the Command A / A-Reasoning / A-Vision trio: it is a single
    # model covering all three (agentic tool use, reasoning, vision), it is Apache 2.0
    # rather than cc-by-nc-4.0, and it is ungated. Flags are from Cohere's own model
    # card: `cohere_command4` for both tool calls and reasoning, which imports the
    # `cohere_melody` package (in the `oss_eval_vllm` extra). Its chat template thinks
    # by default -- `reasoning` is only false when `reasoning_effort` is 'none'.
    #
    # Cohere publishes no unquantized-and-unsuffixed repo; `-bf16` is the reference
    # checkpoint (~437GB, 8xH100). `-fp8` and `-w4a4` are the same model at 4x and 2x
    # H100, and Cohere reports negligible benchmark differences -- point
    # `--local-model-path` at one of those to run this on fewer GPUs.
    "CohereLabs/command-a-plus-05-2026-bf16": OSSModelConfig(
        model_name="CohereLabs/command-a-plus-05-2026-bf16",
        display_name="Command A+",
        url="https://huggingface.co/CohereLabs/command-a-plus-05-2026-bf16",
        org="Cohere",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        supports_image_input=True,
        vllm_tool_call_parser="cohere_command4",
        vllm_reasoning_parser="cohere_command4",
    ),
    # The `Team-ACE/ToolACE-2-8B` repo this entry used to point at does not exist on
    # HF; the ToolACE-2 release is `ToolACE-2-Llama-3.1-8B`, and 2.5 supersedes it.
    # vLLM lists ToolACE under the `pythonic` parser (it emits `[func(arg=val)]`).
    "Team-ACE/ToolACE-2.5-Llama-3.1-8B": OSSModelConfig(
        model_name="Team-ACE/ToolACE-2.5-Llama-3.1-8B",
        display_name="ToolACE-2.5-Llama-3.1-8B",
        url="https://huggingface.co/Team-ACE/ToolACE-2.5-Llama-3.1-8B",
        org="Huawei Noah & USTC",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="pythonic",
    ),
    # Replaces the two MiniCPM3-4B entries, whose bespoke handlers were deleted with
    # the rest of local_inference. The model card only mentions SGLang's `minicpm5`
    # parser, but vLLM registers one under the same name (since v0.23.0).
    # @HuanzhiMao FIXME: served in non-thinking mode on purpose -- MiniCPM5 is hybrid
    # reasoning, but vLLM has a `minicpm5` *tool-call* parser and no matching
    # *reasoning* parser, so with thinking on the `<think>` block lands in content.
    "openbmb/MiniCPM5-1B": OSSModelConfig(
        model_name="openbmb/MiniCPM5-1B",
        display_name="MiniCPM5-1B",
        url="https://huggingface.co/openbmb/MiniCPM5-1B",
        org="openbmb",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="minicpm5",
        inference_request_extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    ),
    # @HuanzhiMao FIXME: `nanbeige` is the parser name the Nanbeige4.2 model card
    # gives, but it is registered in NEITHER vLLM's tool-call nor reasoning registry
    # (checked v0.23.0, v0.25.1, v0.26.0 and main), so `vllm serve` will reject it and
    # this entry cannot run yet. Nanbeige presumably ships it out-of-tree -- if so,
    # add `--tool-parser-plugin <path>` via vllm_extra_serve_args.
    "Nanbeige/Nanbeige4.2-3B": OSSModelConfig(
        model_name="Nanbeige/Nanbeige4.2-3B",
        display_name="Nanbeige4.2-3B",
        url="https://huggingface.co/Nanbeige/Nanbeige4.2-3B",
        org="Nanbeige",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        vllm_tool_call_parser="nanbeige",
        vllm_reasoning_parser="nanbeige",
    ),
    # Both GLM-V entries were previously served through the Z.ai API; they have MIT open
    # weights and are small enough to host, so we self-host them. The `glm45` parser
    # names come from vLLM's own recipe (recipes.vllm.ai/zai-org/GLM-4.6V), not the
    # model cards, which omit them. Both chat templates think by default.
    #
    # GLM-4.6V is ~215GB in bf16; vLLM's recipe serves the FP8 twin
    # (`zai-org/GLM-4.6V-FP8`) on 4 GPUs -- point `--local-model-path` at it to
    # reproduce with less hardware.
    "zai-org/GLM-4.6V": OSSModelConfig(
        model_name="zai-org/GLM-4.6V",
        display_name="GLM-4.6V",
        url="https://huggingface.co/zai-org/GLM-4.6V",
        org="Zhipu AI",
        license="MIT",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        supports_image_input=True,
        vllm_tool_call_parser="glm45",
        vllm_reasoning_parser="glm45",
    ),
    "zai-org/GLM-4.6V-Flash": OSSModelConfig(
        model_name="zai-org/GLM-4.6V-Flash",
        display_name="GLM-4.6V-Flash",
        url="https://huggingface.co/zai-org/GLM-4.6V-Flash",
        org="Zhipu AI",
        license="MIT",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        supports_image_input=True,
        vllm_tool_call_parser="glm45",
        vllm_reasoning_parser="glm45",
    ),
}

# @HuanzhiMao TODO: Add openai audio models
# https://developers.openai.com/api/docs/models/all#realtime-audio
# add audio support for openai completion.
audio_model_map = {}

# Vision-capable models are not a separate hosting pathway -- they live in the
# api/local maps above and are marked with `supports_image_input=True`. The two
# GLM-4.6V entries that used to sit here are now self-hosted (see the zai-org
# entries in `local_inference_model_map`).
vision_model_map = {}

MODEL_CONFIG_MAPPING: dict[str, ModelConfig] = {
    **api_inference_model_map,
    **local_inference_model_map,
    **vision_model_map,
}

# Pre-computed mappings between registry names (keys in MODEL_CONFIG_MAPPING) and
# their sanitized directory names (safe for file paths on all platforms).
# Both the write side (base_handler) and the read side (eval_runner) should use
# these mappings as the single source of truth.
from bfcl_eval.utils import sanitize_model_name_for_path

REGISTRY_TO_DIR_NAME: dict[str, str] = {
    name: sanitize_model_name_for_path(name) for name in MODEL_CONFIG_MAPPING
}
DIR_NAME_TO_REGISTRY: dict[str, str] = {
    dir_name: name for name, dir_name in REGISTRY_TO_DIR_NAME.items()
}

# @HuanzhiMao TODO: update file on the fly?
# Uncomment the folllowing to get the supported_models.py file contents

# all_model_list = []
# true_audio_model_list = []
# vision_model_list = []
# for key, config in MODEL_CONFIG_MAPPING.items():
#     if config.supports_audio_input:
#         true_audio_model_list.append(key)
#     if config.supports_image_input:
#         vision_model_list.append(key)
#     all_model_list.append(key)

# print("Text supported models:")
# print(repr(all_model_list))
# print("True audio supported models:")
# print(repr(true_audio_model_list))
# print("Vision supported models:")
# print(repr(vision_model_list))


# https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-realtime
# https://docs.bigmodel.cn/cn/guide/models/sound-and-video/glm-4-voice
