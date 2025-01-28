from bfcl.model_handler.api_inference.claude import ClaudeHandler
from bfcl.model_handler.api_inference.cohere import CohereHandler
from bfcl.model_handler.api_inference.databricks import DatabricksHandler
from bfcl.model_handler.api_inference.deepseek import DeepSeekAPIHandler
from bfcl.model_handler.api_inference.fireworks import FireworksHandler
from bfcl.model_handler.api_inference.functionary import FunctionaryHandler
from bfcl.model_handler.api_inference.gemini import GeminiHandler
from bfcl.model_handler.api_inference.gogoagent import GoGoAgentHandler
from bfcl.model_handler.api_inference.gorilla import GorillaHandler
from bfcl.model_handler.api_inference.grok import GrokHandler
from bfcl.model_handler.api_inference.mistral import MistralHandler
from bfcl.model_handler.api_inference.nexus import NexusHandler
from bfcl.model_handler.api_inference.nova import NovaHandler
from bfcl.model_handler.api_inference.nvidia import NvidiaHandler
from bfcl.model_handler.api_inference.openai import OpenAIHandler
from bfcl.model_handler.api_inference.writer import WriterHandler
from bfcl.model_handler.api_inference.yi import YiHandler
from bfcl.model_handler.local_inference.bielik import BielikHandler
from bfcl.model_handler.local_inference.deepseek import DeepseekHandler
from bfcl.model_handler.local_inference.deepseek_coder import DeepseekCoderHandler
from bfcl.model_handler.local_inference.gemma import GemmaHandler
from bfcl.model_handler.local_inference.glaive import GlaiveHandler
from bfcl.model_handler.local_inference.glm import GLMHandler
from bfcl.model_handler.local_inference.granite import GraniteHandler
from bfcl.model_handler.local_inference.hammer import HammerHandler
from bfcl.model_handler.local_inference.hermes import HermesHandler
from bfcl.model_handler.local_inference.llama import LlamaHandler
from bfcl.model_handler.local_inference.llama_fc import LlamaFCHandler
from bfcl.model_handler.local_inference.minicpm import MiniCPMHandler
from bfcl.model_handler.local_inference.minicpm_fc import MiniCPMFCHandler
from bfcl.model_handler.local_inference.mistral_fc import MistralFCHandler
from bfcl.model_handler.local_inference.phi import PhiHandler
from bfcl.model_handler.local_inference.quick_testing_oss import QuickTestingOSSHandler
from bfcl.model_handler.local_inference.qwen import QwenHandler
from bfcl.model_handler.local_inference.salesforce import SalesforceHandler

# TODO: Add meta-llama/Llama-3.1-405B-Instruct

# Inference through API calls
api_inference_handler_map = {
    "DeepSeek-V3": DeepSeekAPIHandler,
    "o1-2024-12-17-FC": OpenAIHandler,
    "o1-2024-12-17": OpenAIHandler,
    "gpt-4o-2024-11-20": OpenAIHandler,
    "gpt-4o-2024-11-20-FC": OpenAIHandler,
    "gpt-4o-mini-2024-07-18": OpenAIHandler,
    "gpt-4o-mini-2024-07-18-FC": OpenAIHandler,
    "gpt-4-turbo-2024-04-09": OpenAIHandler,
    "gpt-4-turbo-2024-04-09-FC": OpenAIHandler,
    "claude-3-opus-20240229": ClaudeHandler,
    "claude-3-opus-20240229-FC": ClaudeHandler,
    "claude-3-5-sonnet-20241022": ClaudeHandler,
    "claude-3-5-sonnet-20241022-FC": ClaudeHandler,
    "claude-3-5-haiku-20241022": ClaudeHandler,
    "claude-3-5-haiku-20241022-FC": ClaudeHandler,
    "nova-pro-v1.0": NovaHandler,
    "nova-lite-v1.0": NovaHandler,
    "nova-micro-v1.0": NovaHandler,
    "open-mistral-nemo-2407": MistralHandler,
    "open-mistral-nemo-2407-FC": MistralHandler,
    "open-mixtral-8x22b": MistralHandler,
    "open-mixtral-8x22b-FC": MistralHandler,
    "open-mixtral-8x7b": MistralHandler,
    "mistral-large-2407": MistralHandler,
    "mistral-large-2407-FC": MistralHandler,
    "gemini-2.0-flash-exp": GeminiHandler,
    "gemini-2.0-flash-exp-FC": GeminiHandler,
    "gemini-1.5-pro-002": GeminiHandler,
    "gemini-1.5-pro-002-FC": GeminiHandler,
    "databricks-dbrx-instruct": DatabricksHandler,
    "command-r7b-12-2024-FC": CohereHandler,
}

# Inference through local hosting
local_inference_handler_map = {
    "google/gemma-2-2b-it": GemmaHandler,
    "google/gemma-2-9b-it": GemmaHandler,
    "google/gemma-2-27b-it": GemmaHandler,
    "meta-llama/Meta-Llama-3-8B-Instruct": LlamaHandler,
    "meta-llama/Meta-Llama-3-70B-Instruct": LlamaHandler,
    "meta-llama/Llama-3.1-8B-Instruct-FC": LlamaFCHandler,
    "meta-llama/Llama-3.1-8B-Instruct": LlamaHandler,
    "meta-llama/Llama-3.1-70B-Instruct-FC": LlamaFCHandler,
    "meta-llama/Llama-3.1-70B-Instruct": LlamaHandler,
    "meta-llama/Llama-3.2-1B-Instruct": LlamaHandler,
    "meta-llama/Llama-3.2-3B-Instruct": LlamaHandler,
    "meta-llama/Llama-3.3-70B-Instruct-FC": LlamaFCHandler,
    "meta-llama/Llama-3.3-70B-Instruct": LlamaHandler,
    "Salesforce/xLAM-1b-fc-r": SalesforceHandler,
    "Salesforce/xLAM-7b-fc-r": SalesforceHandler,
    "Salesforce/xLAM-7b-r": SalesforceHandler,
    "Salesforce/xLAM-8x22b-r": SalesforceHandler,
    "Salesforce/xLAM-8x7b-r": SalesforceHandler,
    "mistralai/Ministral-8B-Instruct-2410": MistralFCHandler,
    "ibm-granite/granite-20b-functioncalling": GraniteHandler,
    "MadeAgents/Hammer2.1-7b": HammerHandler,
    "MadeAgents/Hammer2.1-3b": HammerHandler,
    "MadeAgents/Hammer2.1-1.5b": HammerHandler,
    "MadeAgents/Hammer2.1-0.5b": HammerHandler,
    "Qwen/Qwen2.5-0.5B-Instruct": QwenHandler,
    "Qwen/Qwen2.5-1.5B-Instruct": QwenHandler,
    "Qwen/Qwen2.5-3B-Instruct": QwenHandler,
    "Qwen/Qwen2.5-7B-Instruct": QwenHandler,
    "Qwen/Qwen2.5-14B-Instruct": QwenHandler,
    "Qwen/Qwen2.5-32B-Instruct": QwenHandler,
    "Qwen/Qwen2.5-72B-Instruct": QwenHandler,
    "Team-ACE/ToolACE-8B": LlamaHandler,
    "openbmb/MiniCPM3-4B": MiniCPMHandler,
    "openbmb/MiniCPM3-4B-FC": MiniCPMFCHandler,
    "deepseek-ai/DeepSeek-V2.5": DeepseekCoderHandler,
}

# Deprecated/outdated models, no longer on the leaderboard
outdated_model_handler_map = {
    # "gorilla-openfunctions-v0": GorillaHandler,
    # "o1-preview-2024-09-12": OpenAIHandler,
    # "gpt-4o-2024-08-06": OpenAIHandler,
    # "gpt-4o-2024-08-06-FC": OpenAIHandler,
    # "gpt-4o-2024-05-13": OpenAIHandler,
    # "gpt-4o-2024-05-13-FC": OpenAIHandler,
    # "gpt-4-1106-preview-FC": OpenAIHandler,
    # "gpt-4-1106-preview": OpenAIHandler,
    # "gpt-4-0125-preview-FC": OpenAIHandler,
    # "gpt-4-0125-preview": OpenAIHandler,
    # "gpt-4-0613-FC": OpenAIHandler,
    # "gpt-4-0613": OpenAIHandler,
    # "claude-2.1": ClaudeHandler,
    # "claude-instant-1.2": ClaudeHandler,
    # "claude-3-sonnet-20240229": ClaudeHandler,
    # "claude-3-sonnet-20240229-FC": ClaudeHandler,
    # "claude-3-5-sonnet-20240620": ClaudeHandler,
    # "claude-3-5-sonnet-20240620-FC": ClaudeHandler,
    # "claude-3-haiku-20240307": ClaudeHandler,
    # "claude-3-haiku-20240307-FC": ClaudeHandler,
    # "gemini-1.0-pro-001": GeminiHandler,
    # "gemini-1.0-pro-001-FC": GeminiHandler,
    # "meetkai/functionary-small-v3.1-FC": FunctionaryHandler,
    # "mistral-tiny-2312": MistralHandler,
    # "glaiveai/glaive-function-calling-v1": GlaiveHandler,
    # "google/gemma-7b-it": GemmaHandler,
    # "deepseek-ai/deepseek-coder-6.7b-instruct": DeepseekHandler,
}

HANDLER_MAP = {**api_inference_handler_map, **local_inference_handler_map}
