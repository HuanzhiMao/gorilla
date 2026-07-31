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
from bfcl_eval.model_handler.api_inference.ling import LingAPIHandler
from bfcl_eval.model_handler.api_inference.mimo import MiMoHandler
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
#   4. Rule 2 needs somewhere to send the model. When a >500B model has no first-party
#      API -- only resellers, which put us back to scoring someone's serving stack -- we
#      self-host it instead of routing through an aggregator (see thinkingmachines/Inkling).
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
    # Ling-2.6-1T: MIT weights, 1T total / 50B active, past the self-hosting line, so it
    # runs against Ant's own Bailing/Tbox endpoint. Like Ling-2.6-flash it is an instruct
    # model with no thinking mode.
    # @HuanzhiMao FIXME: two things to confirm on the first run. (1) The API model id --
    # the Tbox platform historically used dated names (`Ling-lite-1.5-250604`), so
    # `Ling-2.6-1T` may need a suffix. (2) Whether that endpoint accepts `tools` at all;
    # the open weights support tool calling, but Tbox's API reference is behind a login.
    "Ling-2.6-1T": ModelConfig(
        model_name="Ling-2.6-1T",
        display_name="Ling-2.6-1T",
        url="https://huggingface.co/inclusionAI/Ling-2.6-1T",
        org="inclusionAI",
        license="MIT",
        model_handler=LingAPIHandler,
        input_price=None,
        output_price=None,
        underscore_to_dot=False,
    ),
    # MiMo-V2.5-Pro has MIT weights, but at 1.02T total / 42B active it is past the point
    # where self-hosting is reproducible, so it goes through Xiaomi's own OpenAI-compatible
    # API. Prices are the official cache-miss input and output rates.
    # @HuanzhiMao FIXME: the platform lists "Deep Thinking" as a capability of
    # `mimo-v2.5-pro` but does not document the toggle, and the open-weight twin ships with
    # thinking off, so `is_reasoning_model` stays False until we can confirm how to turn it
    # on -- then flip this and set the parameter in MiMoHandler.
    "mimo-v2.5-pro": ModelConfig(
        model_name="mimo-v2.5-pro",
        display_name="MiMo-V2.5-Pro",
        url="https://huggingface.co/XiaomiMiMo/MiMo-V2.5-Pro",
        org="Xiaomi",
        license="MIT",
        model_handler=MiMoHandler,
        input_price=0.435,
        output_price=0.87,
        underscore_to_dot=False,
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
    # gpt-oss (Apache 2.0) is text-only and speaks OpenAI's harmony format rather than
    # a plain chat template. vLLM switches to its HarmonyParser purely off the config
    # (`model_type == "gpt_oss"`), so no reasoning parser is set here: the analysis
    # channel already comes back as `reasoning_content`, and `--reasoning-parser` is
    # bypassed on the harmony path. The tool call parser is still needed --
    # `--tool-call-parser openai` (OpenAIToolParser) is what the vLLM recipe uses for
    # user-defined functions. The MXFP4 checkpoints are small for their parameter
    # count: ~61GB for 120b, ~14GB for 20b.
    #
    # Reasoning effort rides in the harmony system message. We run at harmony's default
    # (medium); pass `inference_request_extra_body={"reasoning_effort": "high"}` (only
    # low/medium/high are accepted) to change it.
    #
    # @HuanzhiMao FIXME: harmony stamps the current date into the system message and
    # vLLM has no flag to pin it, so runs are not byte-identical across days.
    "openai/gpt-oss-120b": OSSModelConfig(
        model_name="openai/gpt-oss-120b",
        display_name="gpt-oss-120b",
        url="https://huggingface.co/openai/gpt-oss-120b",
        org="OpenAI",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        vllm_tool_call_parser="openai",
    ),
    "openai/gpt-oss-20b": OSSModelConfig(
        model_name="openai/gpt-oss-20b",
        display_name="gpt-oss-20b",
        url="https://huggingface.co/openai/gpt-oss-20b",
        org="OpenAI",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        vllm_tool_call_parser="openai",
    ),
    # Seed-OSS (Apache 2.0), 36B dense and text-only. vLLM's recipe passes only
    # `--tool-call-parser seed_oss`, but we add the matching `seed_oss` reasoning parser:
    # unlike gpt-oss there is no harmony auto-detection here, just a chat template, so
    # without it the `<seed:think>` block lands in `content`.
    # CoT length is a chat-template kwarg (multiples of 512; 0 answers directly); leaving
    # it unset means an unbudgeted CoT, which is what we score.
    "ByteDance-Seed/Seed-OSS-36B-Instruct": OSSModelConfig(
        model_name="ByteDance-Seed/Seed-OSS-36B-Instruct",
        display_name="Seed-OSS-36B-Instruct",
        url="https://huggingface.co/ByteDance-Seed/Seed-OSS-36B-Instruct",
        org="ByteDance",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        vllm_tool_call_parser="seed_oss",
        vllm_reasoning_parser="seed_oss",
    ),
    # Ling-2.6-flash (MIT) is 107B total / 7.4B active. Ling is the instruct half of the
    # Ling/Ring split -- it does not think -- so there is no reasoning parser and
    # `is_reasoning_model` stays False. The 1T sibling is past the self-hosting line.
    #
    # @HuanzhiMao FIXME: validate `hermes` before publishing a score. vLLM registers no
    # `bailing`/`ling` tool parser (checked main) and the vLLM recipe omits the flag, but
    # the model card's SGLang instructions say `--tool-call-parser qwen25` and the chat
    # template emits hermes-style `<tool_call>{"name": ..., "arguments": ...}</tool_call>`,
    # so `hermes` is the vLLM equivalent.
    "inclusionAI/Ling-2.6-flash": OSSModelConfig(
        model_name="inclusionAI/Ling-2.6-flash",
        display_name="Ling-2.6-flash",
        url="https://huggingface.co/inclusionAI/Ling-2.6-flash",
        org="inclusionAI",
        license="MIT",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="hermes",
    ),
    # MiniMax-M3: 427B total / 26B active, natively multimodal (image + video in), under
    # MiniMax's own community license rather than MIT. `--block-size 128` is mandatory on
    # every platform (MSA sparse/index cache alignment), hence vllm_extra_serve_args.
    # Thinking defaults to `adaptive`, where the model decides per request whether to
    # reason -- that makes runs hard to compare, so we pin it to `enabled`.
    "MiniMaxAI/MiniMax-M3": OSSModelConfig(
        model_name="MiniMaxAI/MiniMax-M3",
        display_name="MiniMax-M3",
        url="https://huggingface.co/MiniMaxAI/MiniMax-M3",
        org="MiniMax",
        license="minimax-community",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        supports_image_input=True,
        vllm_tool_call_parser="minimax_m3",
        vllm_reasoning_parser="minimax_m3",
        vllm_extra_serve_args=["--block-size", "128"],
        inference_request_extra_body={
            "chat_template_kwargs": {"thinking_mode": "enabled"}
        },
    ),
    # Step-3.7-Flash: 201B total / ~11B active vision-language MoE, Apache 2.0.
    # `--disable-cascade-attn` is a correctness requirement, not tuning -- the recipe's
    # troubleshooting section says the hybrid SWA/GA schedule is incompatible with vLLM's
    # cascade attention. The recipe also runs `--enable-expert-parallel` and MTP-3
    # speculative decoding; both are throughput knobs tied to its 8-GPU layout, so they
    # are left out here.
    "stepfun-ai/Step-3.7-Flash": OSSModelConfig(
        model_name="stepfun-ai/Step-3.7-Flash",
        display_name="Step-3.7-Flash",
        url="https://huggingface.co/stepfun-ai/Step-3.7-Flash",
        org="StepFun",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        supports_image_input=True,
        vllm_tool_call_parser="step3p5",
        vllm_reasoning_parser="step3p5",
        vllm_extra_serve_args=["--disable-cascade-attn"],
    ),
    # Hy3 (Tencent): 299B total / 21B active, text-only, Apache 2.0. Chain-of-thought is
    # off by default (`reasoning_effort: "no_think"`); we score reasoning mode, so we send
    # "high" -- the other accepted values are "no_think" and "low".
    "tencent/Hy3": OSSModelConfig(
        model_name="tencent/Hy3",
        display_name="Hy3",
        url="https://huggingface.co/tencent/Hy3",
        org="Tencent",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        vllm_tool_call_parser="hy_v3",
        vllm_reasoning_parser="hy_v3",
        inference_request_extra_body={
            "chat_template_kwargs": {"reasoning_effort": "high"}
        },
    ),
    # Inkling-Small (Apache 2.0): 266B total / 12B active, natively multimodal -- text,
    # image and audio in, text out. The tokenizer is custom, so `--tokenizer-mode inkling`
    # is required. BF16 weights are ~532GB; vLLM's recipe serves the NVFP4 twin
    # (`thinkingmachines/Inkling-Small-NVFP4`, ~180GB) -- point `--local-model-path` at it
    # to reproduce on one node. The 975B Inkling is past the self-hosting line.
    #
    # `supports_audio_input` describes the model, as it does for the gemma-4 entries;
    # OSSHandler still inherits `can_handle_audio_input = False`, so that is what actually
    # gates whether the audio categories run.
    "thinkingmachines/Inkling-Small": OSSModelConfig(
        model_name="thinkingmachines/Inkling-Small",
        display_name="Inkling-Small",
        url="https://huggingface.co/thinkingmachines/Inkling-Small",
        org="Thinking Machines Lab",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        supports_image_input=True,
        supports_audio_input=True,
        vllm_tool_call_parser="inkling",
        vllm_reasoning_parser="inkling",
        vllm_extra_serve_args=["--tokenizer-mode", "inkling"],
    ),
    # Inkling (Apache 2.0): 952B total / 41B active, same modalities and parsers as
    # Inkling-Small. Self-hosted as a deliberate exception to the ~500B rule (rule 4
    # above): Thinking Machines ships no first-party inference API, so the alternative
    # was an aggregator. BF16 is ~1.9TB; vLLM's recipe serves `Inkling-NVFP4` on 4x GB200,
    # so expect to pass `--local-model-path`.
    "thinkingmachines/Inkling": OSSModelConfig(
        model_name="thinkingmachines/Inkling",
        display_name="Inkling",
        url="https://huggingface.co/thinkingmachines/Inkling",
        org="Thinking Machines Lab",
        license="apache-2.0",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        supports_image_input=True,
        supports_audio_input=True,
        vllm_tool_call_parser="inkling",
        vllm_reasoning_parser="inkling",
        vllm_extra_serve_args=["--tokenizer-mode", "inkling"],
    ),
    # MiMo-V2.5 (MIT): 311B total / 15B active omnimodal model -- text, image, video and
    # audio in. Thinking is off unless requested, so we turn it on per request. The 1.02T
    # MiMo-V2.5-Pro is past the self-hosting line and lives in api_inference_model_map.
    "XiaomiMiMo/MiMo-V2.5": OSSModelConfig(
        model_name="XiaomiMiMo/MiMo-V2.5",
        display_name="MiMo-V2.5",
        url="https://huggingface.co/XiaomiMiMo/MiMo-V2.5",
        org="Xiaomi",
        license="MIT",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        supports_image_input=True,
        supports_audio_input=True,
        vllm_tool_call_parser="mimo",
        vllm_reasoning_parser="mimo",
        inference_request_extra_body={
            "chat_template_kwargs": {"enable_thinking": True}
        },
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
