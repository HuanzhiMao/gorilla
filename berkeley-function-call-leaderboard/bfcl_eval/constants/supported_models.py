# -----------------------------------------------------------------------------
# Supported Model Index  •  Convenience helper
#
# The canonical model-config mapping lives in `model_config.py` and is ~2000
# lines long. Navigating that file just to see whether a model key exists was
# getting painful, so this lightweight companion keeps **only** the keys in a
# flat list so you can:
#
#   •  skim the supported models at a glance;
#   •  hit ⌘/Ctrl-F and jump straight to the one you need;
#   •  import the list in quick scripts/tests without hauling in the whole
#      config (e.g. `if model_name in SUPPORTED_MODELS:`).
# -----------------------------------------------------------------------------
SUPPORTED_MODELS = [
    "DeepSeek-V4-Pro",
    "DeepSeek-V4-Flash",
    "gpt-5.6-sol",
    "gpt-5.6-terra",
    "gpt-5.6-luna",
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-haiku-4-5-20251001",
    "muse-spark-1.1",
    "nova-pro-v1.0",
    "nova-2-lite-v1.0",
    "nova-micro-v1.0",
    "mistral-large-2512",
    "gemini-3.1-flash-lite-preview",
    "gemini-3.5-flash",
    "gemini-3.1-pro-preview",
    "palmyra-x5",
    "grok-4.5",
    "glm-5.2",
    "glm-5v-turbo",
    "kimi-k3",
    "Nanbeige3.5-Pro-Thinking",
    "google/gemma-4-E2B-it",
    "google/gemma-4-E4B-it",
    "google/gemma-4-26B-A4B-it",
    "google/gemma-4-31B-it",
    "google/functiongemma-270m-it",
    "meta-llama/Llama-4-Scout-17B-16E-Instruct",
    "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8",
    "Salesforce/Llama-xLAM-2-70b-fc-r",
    "Salesforce/Llama-xLAM-2-8b-fc-r",
    "Salesforce/xLAM-2-32b-fc-r",
    "Salesforce/xLAM-2-3b-fc-r",
    "Salesforce/xLAM-2-1b-fc-r",
    "mistralai/Mistral-Medium-3.5-128B",
    "mistralai/Mistral-Small-4-119B-2603",
    "microsoft/Phi-4-mini-instruct",
    "ibm-granite/granite-3.2-8b-instruct",
    "ibm-granite/granite-3.1-8b-instruct",
    "ibm-granite/granite-4.0-350m",
    "MadeAgents/Hammer2.1-7b",
    "MadeAgents/Hammer2.1-3b",
    "MadeAgents/Hammer2.1-1.5b",
    "MadeAgents/Hammer2.1-0.5b",
    "Qwen/Qwen3.5-0.8B",
    "Qwen/Qwen3.5-2B",
    "Qwen/Qwen3.5-4B",
    "Qwen/Qwen3.5-9B",
    "Qwen/Qwen3.6-27B",
    "Qwen/Qwen3.6-35B-A3B",
    "Qwen/Qwen3.5-122B-A10B",
    "Qwen/Qwen3.5-397B-A17B",
    "CohereLabs/command-a-plus-05-2026-bf16",
    "Team-ACE/ToolACE-2.5-Llama-3.1-8B",
    "openbmb/MiniCPM5-1B",
    "Nanbeige/Nanbeige4.2-3B",
    "zai-org/GLM-4.6V",
    "zai-org/GLM-4.6V-Flash",
]
