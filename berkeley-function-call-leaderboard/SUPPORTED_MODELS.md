# Table of Supported Models

Below is a comprehensive table of models supported for running leaderboard evaluations. Each model entry indicates whether it supports native Function Calling (FC) or requires a special prompt format to generate function calls. Models marked with `💻` are intended to be hosted locally (using vllm or sglang), while models without the `💻` icon are accessed via API calls. To quickly see all available models, you can also run the `bfcl models` command.

**Note:**  

- **Function Calling (FC)** models directly support the function calling schema as documented by their respective providers.
- **Prompt** models do not natively support function calling. For these, we supply a consistent system message prompting the model to produce function calls in the desired format.

| Base Model | Version | Type | Provider | Name in BFCL |
|---|---|---|---|---|
| Arctic | ? | Prompt | Snowflake | snowflake/arctic |
| Bielik | v2.3 (11b) | Prompt | Self-hosted | speakleash/Bielik-11B-v2.3-Instruct 💻 |
| BitAgent | (8b) | Prompt | Self-hosted | BitAgent/BitAgent-8B 💻 |
| ChatGPT | 3.5 Turbo | Function Calling | OpenAI | gpt-3.5-turbo-0125-FC |
| ChatGPT | 3.5 Turbo | Prompt | OpenAI | gpt-3.5-turbo-0125 |
| ChatGPT | 4 Turbo | Function Calling | OpenAI | gpt-4-turbo-2024-04-09-FC |
| ChatGPT | 4 Turbo | Prompt | OpenAI | gpt-4-turbo-2024-04-09 |
| ChatGPT | 4o | Function Calling | OpenAI | gpt-4o-2024-11-20-FC |
| ChatGPT | 4o | Prompt | OpenAI | gpt-4o-2024-11-20 |
| ChatGPT | 4o mini | Function Calling | OpenAI | gpt-4o-mini-2024-07-18-FC |
| ChatGPT | 4o mini | Prompt | OpenAI | gpt-4o-mini-2024-07-18 |
| ChatGPT | 4.5 Preview | Function Calling | OpenAI | gpt-4.5-preview-2025-02-27-FC |
| ChatGPT | 4.5 Preview | Prompt | OpenAI | gpt-4.5-preview-2025-02-27 |
| ChatGPT | o1 | Function Calling | OpenAI | o1-2024-12-17-FC |
| ChatGPT | o1 | Prompt | OpenAI | o1-2024-12-17 |
| ChatGPT | o3 mini | Function Calling | OpenAI | o3-mini-2025-01-31-FC |
| ChatGPT | o3 mini | Prompt | OpenAI | o3-mini-2025-01-31 |
| Claude | 3 Opus | Function Calling | Anthropic |claude-3-opus-20240229-FC |
| Claude | 3 Opus | Prompt | Anthropic |claude-3-opus-20240229 |
| Claude | 3.7 Sonnet | Function Calling | Anthropic | claude-3-7-sonnet-20250219-FC |
| Claude | 3.7 Sonnet | Prompt | Anthropic | claude-3-7-sonnet-20250219 |
| Claude | 3.5 Sonnet | Function Calling | Anthropic | claude-3-5-sonnet-20241022-FC |
| Claude | 3.5 Sonnet | Prompt | Anthropic | claude-3-5-sonnet-20241022 |
| Claude | 3.5 Haiku | Function Calling | Anthropic | claude-3-5-haiku-20241022-FC |
| Claude | 3.5 Haiku | Prompt | Anthropic | claude-3-5-haiku-20241022 |
| CoALM | (8b, 70b, 405b) | Function Calling | Self-hosted | uiuc-convai/CoALM-{8B,70B,405B} 💻 |
| Command R | Plus | Function Calling | Cohere | command-r-plus-FC |
| Command R | (7b) | Function Calling | Cohere | command-r7b-12-2024-FC |
| DeepSeek | R1 | Prompt | Hangzhou DeepSeek AI Basic Technology Research Co. | DeepSeek-R1 |
| DeepSeek | v3 | Function Calling | Hangzhou DeepSeek AI Basic Technology Research Co. | DeepSeek-V3-FC |
| DeepSeek | R1 | Prompt | Self-hosted | deepseek-ai/DeepSeek-R1 💻 |
| DeepSeek | v2.5 | Function Calling | Self-hosted | deepseek-ai/DeepSeek-V2.5 💻 |
| DeepSeek | v2 (Chat, Lite-Chat) | Prompt | Self-hosted | deepseek-ai/DeepSeek-V2-{Chat-0628,Lite-Chat} 💻 |
| DeepSeek | v2 (Instruct, Lite-Instruct) | Function Calling | Self-hosted | deepseek-ai/DeepSeek-Coder-V2-{Instruct-0724,Lite-Instruct} 💻 |
| DRBX | ? | Prompt | Databricks | databrick-dbrx-instruct |
| Falcon | 3 (1b, 3b, 7b, 10b) | Function Calling | Self-hosted | tiiuae/Falcon3-{1B,3B,7B,10B}-Instruct 💻 |
| Firefunction | (v1, v2) | Function Calling | Fireworks AI | firefunction-{v1,v2}-FC |
| Functionary | (Medium, Small) v3.1 | Function Calling | MeetKai | meetkai/functionary-{small,medium}-v3.1-FC |
| Gemini | 2.0 Flash Thinking | Prompt | Google DeepMind | gemini-2.0-flash-thinking-exp-01-21 |
| Gemini | 2.0 Pro Experimental | Function Calling | Google DeepMind | gemini-2.0-pro-exp-02-05-FC |
| Gemini | 2.0 Pro Experimental | Prompt | Google DeepMind | gemini-2.0-pro-exp-02-05 |
| Gemini | 2.0 Flash | Function Calling | Google DeepMind | gemini-2.0-flash-001-FC |
| Gemini | 2.0 Flash | Prompt | Google DeepMind | gemini-2.0-flash-001 |
| Gemini | 2.0 Flash Lite | Function Calling | Google DeepMind | gemini-2.0-flash-lite-001-FC |
| Gemini | 2.0 Flash Lite | Prompt | Google DeepMind | gemini-2.0-flash-lite-001 |
| Gemma | 2 (2b, 9b, 27b) | Prompt | Self-hosted |google/gemma-2-{2b,9b,27b}-it 💻 |
| GLM | 4 (9b) | Function Calling | Self-hosted | HUDM/glm-4-9b-chat 💻 |
| Gorilla | OpenFunctions v2 | Function Calling | Gorilla LLM | gorilla-openfunctions-v2 |
| Granite | (20b) | Function Calling | Self-hosted | ibm-granite/granite-20b-functioncalling 💻 |
| Grok | Beta | Function Calling | xAI | grok-beta |
| Haha | (7b) | Prompt | Self-hosted | ZJared/Haha-7B 💻 |
| Hammer | 2.1 (7b, 3b, 1.5b, 0.5b) | Function Calling | Self-hosted | MadeAgents/Hammer2.1-{7b,3b,1.5b,0.5b} 💻 |
| Hermes | 2 Pro (Llama 3) | Function Calling | Self-hosted | NousResearch/Hermes-2-Pro-Llama-3-{8B,70B} 💻 |
| Hermes | 2 Pro (Mistral 7b) | Function Calling | Self-hosted | NousResearch/Hermes-2-Pro-Mistral-7B 💻 |
| Hermes | 2 Theta (Llama 3) | Function Calling | Self-hosted | NousResearch/Hermes-2-Theta-Llama-3-{8B,70B} 💻 |
| Llama | 3 (8b, 70b) | Prompt | Self-hosted | meta-llama/Meta-Llama-3-{8B,70B}-Instruct 💻 |
| Llama | 3.1 (8b, 70b) | Function Calling | Self-hosted | meta-llama/Llama-3.1-{8B,70B}-Instruct-FC 💻 |
| Llama | 3.1 (8b, 70b) | Prompt | Self-hosted | meta-llama/Llama-3.1-{8B,70B}-Instruct 💻 |
| Llama | 3.2 (1b, 3b) | Prompt | Self-hosted | meta-llama/Llama-3.2-{1B,3B}-Instruct 💻 |
| Llama | 3.3 (70b) | Prompt | Self-hosted | meta-llama/Llama-3.3-70B-Instruct 💻 |
| Llama | 3.3 (70b) | Function Calling | Self-hosted | meta-llama/Llama-3.3-70B-Instruct-FC 💻 |
| MiniCPM | 3 (4b) | Function Calling | Self-hosted | openbmb/MiniCPM3-4B-FC 💻 |
| MiniCPM | 3 (4b) | Prompt | Self-hosted | openbmb/MiniCPM3-4B 💻 |
| Mistral | Mixtral (8x7b, 8x22b) | Prompt | Mistral AI | open-mixtral-{8x7b,8x22b} |
| Mistral | Mixtral (8x22b) | Function Calling | Mistral AI | open-mixtral-8x22b-FC |
| Mistral | Nemo | Prompt | Mistral AI | open-mistral-nemo-2407 |
| Mistral | Nemo | Function Calling | Mistral AI | open-mistral-nemo-2407-FC |
| Mistral | Large | Function Calling | Mistral AI | mistral-large-2407-FC |
| Mistral | Large | Prompt | Mistral AI | mistral-large-2407 |
| Mistral | Medium | Prompt | Mistral AI | mistral-medium-2312 |
| Mistral | Small | Function Calling | Mistral AI | mistral-small-2402-FC |
| Mistral | Small | Prompt | Mistral AI | mistral-small-2402 |
| Mistral | Tiny | Prompt | Mistral AI | mistral-tiny-2312 |
| Mistral | 8b | Function Calling | Self-hosted | mistralai/Ministral-8B-Instruct-2410 💻 |
| Nemotron | 4 (340b) | Prompt | Nvidia | nvidia/nemotron-4-340b-instruct |
| Nova | Pro v1.0 | Function Calling | ​Amazon Web Services | nova-pro-v1.0|
| Nova | Lite v1.0 | Function Calling | ​Amazon Web Services | nova-lite-v1.0|
| Nova | Macro v1.0 | Function Calling | ​Amazon Web Services | nova-macro-v1.0|
| Palmyra | x | Function Calling | Writer | palmyra-x-004 |
| Phi | 3.5 Mini | Prompt | Self-hosted | microsoft/Phi-3.5-mini-instruct 💻 |
| Phi | 3 Medium (4k, 128k) | Prompt | Self-hosted | microsoft/Phi-3-medium-{4k,128k}-instruct 💻 |
| Phi | 3 Small (8k, 128k) | Prompt | Self-hosted | microsoft/Phi-3-small-{8k,128k}-instruct 💻 |
| Phi | 3 Mini (4k, 128k) | Prompt | Self-hosted | microsoft/Phi-3-mini-{4k,128k}-instruct 💻 |
| Qwen | 2.5 (0.5b, 1.5b, 3b, 7b, 14b, 32b, 72b) | Prompt | Self-hosted | Qwen/Qwen2.5-{0.5B,1.5B,3B,7B,14B,32B,72B}-Instruct 💻 |
| Qwen | 2.5 (0.5b, 1.5b, 3b, 7b, 14b, 32b, 72b) | Function Calling | Self-hosted | Qwen/Qwen2.5-{0.5B,1.5B,3B,7B,14B,32B,72B}-Instruct-FC 💻 |
| Qwen | QwQ (32b) | Prompt | Self-hosted | Qwen/QwQ-32B-Preview 💻 |
| Raven | v2 | Function Calling | Nexusflow | Nexusflow-Raven-v2 |
| Sky | T1 (32b) | Prompt | Self-hosted | NovaSky-AI/Sky-T1-32B-Preview 💻 |
| ToolACE | (8b) | Function Calling | Self-hosted | Team-ACE/ToolACE-8B 💻 |
| Watt Tool | (8b, 70b) | Function Calling | Self-hosted | watt-ai/watt-tool-{8B,70B} 💻 |
| xLAM | (1b) | Function Calling | Self-hosted | Salesforce/xLAM-1b-fc-r 💻 |
| xLAM | (7b) | Function Calling | Self-hosted | Salesforce/xLAM-7b-fc-r 💻 |
| xLAM | (7b) | Function Calling | Self-hosted | Salesforce/xLAM-7b-r 💻 |
| xLAM | (8x7b) | Function Calling | Self-hosted | Salesforce/xLAM-8x7b-r 💻 |
| xLAM | (8x22b) | Function Calling | Self-hosted | Salesforce/xLAM-8x22b-r 💻 |
| Yi | Large | Function Calling | 01.AI | yi-large-fc |
| ? | ? | Prompt | ? | BitAgent/GoGoAgent |

---

## Understanding Versioned Models

For model names containing `{...}`, multiple versions are available. For example, `meta-llama/Llama-3.1-{8B,70B}-Instruct` means we support both models: `meta-llama/Llama-3.1-8B-Instruct` and `meta-llama/Llama-3.1-70B-Instruct`.

## Additional Requirements for Certain Models

- **Gemini Models:**  
  For `Gemini` models, we use the Google Vertex AI endpoint for inference. Ensure you have set the `VERTEX_AI_PROJECT_ID` and `VERTEX_AI_LOCATION` in your `.env` file.

- **Databricks Models:**  
  For `databrick-dbrx-instruct`, you must create an Azure Databricks workspace and set up a dedicated inference endpoint. Provide the endpoint URL via `DATABRICKS_AZURE_ENDPOINT_URL` in `.env`.

- **Nova Models (AWS Bedrock):**  
  For `Nova` models, set your `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in your `.env` file. Make sure the necessary AWS Bedrock permissions are granted in the `us-east-1` region.

---

For more details and a summary of feature support across different models, see the [Berkeley Function Calling Leaderboard blog post](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html#prompt).

