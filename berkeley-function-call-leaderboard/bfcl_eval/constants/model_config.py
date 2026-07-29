from dataclasses import dataclass, field
from re import S
from typing import Optional

from bfcl_eval.model_handler.api_inference.claude import ClaudeHandler
from bfcl_eval.model_handler.api_inference.cohere import CohereHandler
from bfcl_eval.model_handler.api_inference.deepseek import DeepSeekAPIHandler
from bfcl_eval.model_handler.api_inference.gemini import GeminiHandler
from bfcl_eval.model_handler.api_inference.glm import GLMAPIHandler
from bfcl_eval.model_handler.api_inference.gorilla import GorillaHandler
from bfcl_eval.model_handler.api_inference.grok import GrokHandler
from bfcl_eval.model_handler.api_inference.kimi import KimiHandler
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
        input_price=0.8,
        output_price=4,
        underscore_to_dot=True,
        supports_image_input=True,
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
    # @HuanzhiMao FIXME: check mistral implementation
    "mistral-medium-3-5": OSSModelConfig(
        model_name="mistral-medium-3-5",
        display_name="Mistral-Medium-3.5",
        url="https://docs.mistral.ai/guides/model-selection/",
        org="Mistral AI",
        license="Proprietary",
        model_handler=MistralHandler,
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
    # @HuanzhiMao FIXME: Update qwen series
    # "qwen3-0.6b-FC": ModelConfig(
    #     model_name="qwen3-0.6b",
    #     display_name="Qwen3-0.6B (FC)",
    #     url="https://huggingface.co/Qwen/Qwen3-0.6B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=True,
    #     underscore_to_dot=True,
    # ),
    # "qwen3-0.6b": ModelConfig(
    #     model_name="qwen3-0.6b",
    #     display_name="Qwen3-0.6B (Prompt)",
    #     url="https://huggingface.co/Qwen/Qwen3-0.6B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
    # "qwen3-1.7b-FC": ModelConfig(
    #     model_name="qwen3-1.7b",
    #     display_name="Qwen3-1.7B (FC)",
    #     url="https://huggingface.co/Qwen/Qwen3-1.7B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=True,
    #     underscore_to_dot=True,
    # ),
    # "qwen3-1.7b": ModelConfig(
    #     model_name="qwen3-1.7b",
    #     display_name="Qwen3-1.7B (Prompt)",
    #     url="https://huggingface.co/Qwen/Qwen3-1.7B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
    # "qwen3-4b-FC": ModelConfig(
    #     model_name="qwen3-4b",
    #     display_name="Qwen3-4B (FC)",
    #     url="https://huggingface.co/Qwen/Qwen3-4B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=True,
    #     underscore_to_dot=True,
    # ),
    # "qwen3-4b": ModelConfig(
    #     model_name="qwen3-4b",
    #     display_name="Qwen3-4B (Prompt)",
    #     url="https://huggingface.co/Qwen/Qwen3-4B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
    # "qwen3-8b-FC": ModelConfig(
    #     model_name="qwen3-8b",
    #     display_name="Qwen3-8B (FC)",
    #     url="https://huggingface.co/Qwen/Qwen3-8B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=True,
    #     underscore_to_dot=True,
    # ),
    # "qwen3-8b": ModelConfig(
    #     model_name="qwen3-8b",
    #     display_name="Qwen3-8B (Prompt)",
    #     url="https://huggingface.co/Qwen/Qwen3-8B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
    # "qwen3-14b-FC": ModelConfig(
    #     model_name="qwen3-14b",
    #     display_name="Qwen3-14B (FC)",
    #     url="https://huggingface.co/Qwen/Qwen3-14B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=True,
    #     underscore_to_dot=True,
    # ),
    # "qwen3-14b": ModelConfig(
    #     model_name="qwen3-14b",
    #     display_name="Qwen3-14B (Prompt)",
    #     url="https://huggingface.co/Qwen/Qwen3-14B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
    # "qwen3-32b-FC": ModelConfig(
    #     model_name="qwen3-32b",
    #     display_name="Qwen3-32B (FC)",
    #     url="https://huggingface.co/Qwen/Qwen3-32B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=True,
    #     underscore_to_dot=True,
    # ),
    # "qwen3-32b": ModelConfig(
    #     model_name="qwen3-32b",
    #     display_name="Qwen3-32B (Prompt)",
    #     url="https://huggingface.co/Qwen/Qwen3-32B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
    # "qwen3-30b-a3b-instruct-2507-FC": ModelConfig(
    #     model_name="qwen3-30b-a3b-instruct-2507",
    #     display_name="Qwen3-30B-A3B-Instruct-2507 (FC)",
    #     url="https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=True,
    #     underscore_to_dot=True,
    # ),
    # "qwen3-30b-a3b-instruct-2507": ModelConfig(
    #     model_name="qwen3-30b-a3b-instruct-2507",
    #     display_name="Qwen3-30B-A3B-Instruct-2507 (Prompt)",
    #     url="https://huggingface.co/Qwen/Qwen3-30B-A3B-Instruct-2507",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
    # "qwen3-235b-a22b-instruct-2507-FC": ModelConfig(
    #     model_name="qwen3-235b-a22b-instruct-2507",
    #     display_name="Qwen3-235B-A22B-Instruct-2507 (FC)",
    #     url="https://huggingface.co/Qwen/Qwen3-235B-A22B-Instruct-2507",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=True,
    #     underscore_to_dot=False,
    # ),
    # "qwen3-235b-a22b-instruct-2507": ModelConfig(
    #     model_name="qwen3-235b-a22b-instruct-2507",
    #     display_name="Qwen3-235B-A22B-Instruct-2507 (Prompt)",
    #     url="https://huggingface.co/Qwen/Qwen3-235B-A22B-Instruct-2507",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
    # "qwq-32b-FC": ModelConfig(
    #     model_name="qwq-32b",
    #     display_name="QwQ-32B (FC)",
    #     url="https://huggingface.co/Qwen/QwQ-32B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=True,
    #     underscore_to_dot=True,
    # ),
    # "qwq-32b": ModelConfig(
    #     model_name="qwq-32b",
    #     display_name="QwQ-32B (Prompt)",
    #     url="https://huggingface.co/Qwen/QwQ-32B",
    #     org="Qwen",
    #     license="apache-2.0",
    #     model_handler=QwenAPIHandler,
    #     input_price=None,
    #     output_price=None,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
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
    "deepseek-ai/DeepSeek-V4-Pro": OSSModelConfig(
        model_name="deepseek-ai/DeepSeek-V4-Pro",
        display_name="DeepSeek-V4-Pro (self-hosted)",
        url="https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro",
        org="DeepSeek",
        license="MIT",
        model_handler=OSSHandler,
        is_reasoning_model=True,
        underscore_to_dot=False,
        vllm_tool_call_parser="deepseek_v4",
        # @HuanzhiMao FIXME: reasoning parser name inferred, not yet validated on a real run
        vllm_reasoning_parser="deepseek_v4",
        inference_request_extra_body={"chat_template_kwargs": {"thinking": True}},
    ),
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
    "meta-llama/Llama-3.2-1B-Instruct": OSSModelConfig(
        model_name="meta-llama/Llama-3.2-1B-Instruct",
        display_name="Llama-3.2-1B-Instruct",
        url="https://llama.meta.com/llama3",
        org="Meta",
        license="Meta Llama 3 Community",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="llama3_json",
    ),
    "meta-llama/Llama-3.2-3B-Instruct": OSSModelConfig(
        model_name="meta-llama/Llama-3.2-3B-Instruct",
        display_name="Llama-3.2-3B-Instruct",
        url="https://llama.meta.com/llama3",
        org="Meta",
        license="Meta Llama 3 Community",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        vllm_tool_call_parser="llama3_json",
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
    "mistralai/Mistral-Large-3-675B-Instruct-2512": OSSModelConfig(
        model_name="mistralai/Mistral-Large-3-675B-Instruct-2512",
        display_name="Mistral-Large-3-675B-Instruct-2512",
        url="https://huggingface.co/mistralai/Mistral-Large-3-675B-Instruct-2512",
        org="Mistral AI",
        license="apache-2.0",
        model_handler=OSSHandler,
        underscore_to_dot=False,
        supports_image_input=True,
        vllm_tool_call_parser="mistral",
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
    "mistral-small-2603": OSSModelConfig(
        model_name="mistral-small-2603",
        display_name="Mistral-small-2603",
        url="https://docs.mistral.ai/guides/model-selection/",
        org="Mistral AI",
        license="Proprietary",
        model_handler=MistralHandler,
        underscore_to_dot=True,
        supports_image_input=True,
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
    "CohereLabs/command-a-reasoning-08-2025": OSSModelConfig(
        model_name="CohereLabs/command-a-reasoning-08-2025",
        display_name="Command A Reasoning",
        url="https://huggingface.co/CohereLabs/command-a-reasoning-08-2025",
        org="Cohere",
        license="cc-by-nc-4.0",
        model_handler=CohereHandler,
        underscore_to_dot=True,
    ),
    "CohereLabs/c4ai-command-a-03-2025": OSSModelConfig(
        model_name="CohereLabs/c4ai-command-a-03-2025",
        display_name="Command A",
        url="https://huggingface.co/CohereLabs/c4ai-command-a-03-2025",
        org="Cohere",
        license="cc-by-nc-4.0",
        model_handler=CohereHandler,
        underscore_to_dot=True,
    ),
    "CohereLabs/command-a-vision-07-2025": OSSModelConfig(
        model_name="CohereLabs/command-a-vision-07-2025",
        display_name="Command A Vision",
        url="https://huggingface.co/CohereLabs/command-a-vision-07-2025",
        org="Cohere",
        license="cc-by-nc-4.0",
        model_handler=CohereHandler,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    # "Team-ACE/ToolACE-2-8B": OSSModelConfig(
    #     model_name="Team-ACE/ToolACE-2-8B",
    #     display_name="ToolACE-2-8B (FC)",
    #     url="https://huggingface.co/Team-ACE/ToolACE-2-8B",
    #     org="Huawei Noah & USTC",
    #     license="Apache-2.0",
    #     model_handler=LlamaHandler,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
    # "openbmb/MiniCPM3-4B": OSSModelConfig(
    #     model_name="openbmb/MiniCPM3-4B",
    #     display_name="MiniCPM3-4B (Prompt)",
    #     url="https://huggingface.co/openbmb/MiniCPM3-4B",
    #     org="openbmb",
    #     license="Apache-2.0",
    #     model_handler=MiniCPMHandler,
    #     is_fc_model=False,
    #     underscore_to_dot=False,
    # ),
    # "openbmb/MiniCPM3-4B-FC": OSSModelConfig(
    #     model_name="openbmb/MiniCPM3-4B",
    #     display_name="MiniCPM3-4B-FC (FC)",
    #     url="https://huggingface.co/openbmb/MiniCPM3-4B",
    #     org="openbmb",
    #     license="Apache-2.0",
    #     model_handler=MiniCPMFCHandler,
    #     is_fc_model=True,
    #     underscore_to_dot=True,
    # ),

    # "Nanbeige/Nanbeige4-3B-Thinking-2511": OSSModelConfig(
    #     model_name="Nanbeige/Nanbeige4-3B-Thinking-2511",
    #     display_name="Nanbeige4-3B-Thinking-2511 (FC)",
    #     url="https://huggingface.co/Nanbeige/Nanbeige4-3B-Thinking-2511",
    #     org="Nanbeige",
    #     license="apache-2.0",
    #     model_handler=NanbeigeFCHandler,
    #     is_fc_model=True,
    #     underscore_to_dot=False,
    # ),
}

# Inference through third-party inference platforms for open-source models
third_party_inference_model_map = {
    # Via Qwen Agent Framework
    "qwen3-4b-think": ModelConfig(
        model_name="qwen3-4b-think",
        display_name="Qwen3-4B-Think",
        url="https://huggingface.co/Qwen/Qwen3-4B",
        org="Qwen",
        license="apache-2.0",
        model_handler=QwenAgentThinkHandler,
        input_price=None,
        output_price=None,
        underscore_to_dot=True,
    ),
    "qwen3-4b-nothink": ModelConfig(
        model_name="qwen3-4b-nothink",
        display_name="Qwen3-4B-NoThink",
        url="https://huggingface.co/Qwen/Qwen3-4B",
        org="Qwen",
        license="apache-2.0",
        model_handler=QwenAgentNoThinkHandler,
        input_price=None,
        output_price=None,
        underscore_to_dot=True,
    ),
}

# @HuanzhiMao TODO: Add openai audio models
# https://developers.openai.com/api/docs/models/all#realtime-audio
# add audio support for openai completion.
audio_model_map = {}

vision_model_map = {
    "glm-4.6v": ModelConfig(
        model_name="glm-4.6v",
        display_name="GLM-4.6v",
        url="https://huggingface.co/zai-org/GLM-4.6",
        org="Zhipu AI",
        license="MIT",
        model_handler=GLMAPIHandler,
        input_price=None,
        output_price=None,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
    "glm-4.6v-flash": ModelConfig(
        model_name="glm-4.6v-flash",
        display_name="GLM-4.6v-Flash",
        url="https://huggingface.co/zai-org/GLM-4.6v-Flash",
        org="Zhipu AI",
        license="MIT",
        model_handler=GLMAPIHandler,
        input_price=None,
        output_price=None,
        underscore_to_dot=True,
        supports_image_input=True,
    ),
}

MODEL_CONFIG_MAPPING: dict[str, ModelConfig] = {
    **api_inference_model_map,
    **local_inference_model_map,
    **third_party_inference_model_map,
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
