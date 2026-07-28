# Table of Supported Models

Below is a comprehensive table of models supported for running leaderboard evaluations. Every model is evaluated through its native Function Calling (FC) interface. Models marked with `💻` are intended to be hosted locally (using vllm or sglang), while models without the `💻` icon are accessed via API calls. To quickly see all available models, you can also run the `bfcl models` command.

## Understanding Versioned Models

For model names containing `{...}`, multiple versions are available. For example, `meta-llama/Llama-3.1-{8B,70B}-Instruct` means we support both models: `meta-llama/Llama-3.1-8B-Instruct` and `meta-llama/Llama-3.1-70B-Instruct`.

| Base Model                             | Type             | Provider       | Model ID on BFCL                                            |
| -------------------------------------- | ---------------- | -------------- | ----------------------------------------------------------- |
| Amazon-Nova-2-Lite-v1:0                | Function Calling | Amazon         | nova-2-lite-v1.0                                            |
| Amazon-Nova-Micro-v1:0                 | Function Calling | Amazon         | nova-micro-v1.0                                             |
| Amazon-Nova-Pro-v1:0                   | Function Calling | Amazon         | nova-pro-v1.0                                               |
| Arch-Agent-{1.5B,3B,7B,32B}            | Function Calling | Self-hosted 💻 | katanemo/Arch-Agent-{1.5B,3B,7B,32B}                        |
| BitAgent-Bounty-8B                     | Function Calling | Self-hosted 💻 | BitAgent/BitAgent-Bounty-8B                                 |
| claude-3.5-haiku-20241022              | Function Calling | Anthropic      | claude-haiku-4-5-20251001-FC                                |
| Claude-Opus-4.5-20251101               | Function Calling | Anthropic      | claude-opus-4-5-20251101-FC                                 |
| Claude-Sonnet-4.5-20250929             | Function Calling | Anthropic      | claude-sonnet-4-5-20250929-FC                               |
| Command A                              | Function Calling | Cohere         | command-a-03-2025-FC                                        |
| Command A Reasoning                    | Function Calling | Cohere         | command-a-reasoning-08-2025-FC                              |
| Command R7B                            | Function Calling | Cohere         | command-r7b-12-2024-FC                                      |
| DeepSeek-V3.2-Exp                      | Function Calling | DeepSeek       | DeepSeek-V3.2-Exp-FC                                        |
| Falcon3-{1B,3B,7B,10B}-Instruct        | Function Calling | Self-hosted 💻 | tiiuae/Falcon3-{1B,3B,7B,10B}-Instruct-FC                   |
| FireFunction-v2                        | Function Calling | Fireworks      | firefunction-v2-FC                                          |
| Functionary-Medium-v3.1                | Function Calling | MeetKai        | meetkai/functionary-medium-v3.1-FC                          |
| Functionary-Small-v3.1                 | Function Calling | MeetKai        | meetkai/functionary-small-v3.1-FC                           |
| Gemini-2.5-Flash                       | Function Calling | Google         | gemini-2.5-flash-FC                                         |
| Gemini-2.5-Flash-Lite                  | Function Calling | Google         | gemini-2.5-flash-lite-FC                                    |
| Gemini-3-Pro-Preview                   | Function Calling | Google         | gemini-3-pro-preview-FC                                     |
| FunctionGemma-270m-it                  | Function Calling | Self-hosted 💻 | google/functiongemma-270m-it-FC                             |
| GLM-4-9b-Chat                          | Function Calling | Self-hosted 💻 | THUDM/glm-4-9b-chat                                         |
| GLM-4.5                                | Function Calling | Zhipu AI       | glm-4.5-FC                                                  |
| GLM-4.5-Air                            | Function Calling | Zhipu AI       | glm-4.5-air-FC                                              |
| GLM-4.6                                | Function Calling | Zhipu AI       | glm-4.6-FC                                                  |
| Gorilla-OpenFunctions-v2               | Function Calling | Gorilla LLM    | gorilla-openfunctions-v2                                    |
| GPT-4.1-2025-04-14                     | Function Calling | OpenAI         | gpt-4.1-2025-04-14-FC                                       |
| GPT-4.1-mini-2025-04-14                | Function Calling | OpenAI         | gpt-4.1-mini-2025-04-14-FC                                  |
| GPT-4.1-nano-2025-04-14                | Function Calling | OpenAI         | gpt-4.1-nano-2025-04-14-FC                                  |
| GPT-4o-2024-11-20                      | Function Calling | OpenAI         | gpt-4o-2024-11-20-FC                                        |
| GPT-4o-mini-2024-07-18                 | Function Calling | OpenAI         | gpt-4o-mini-2024-07-18-FC                                   |
| GPT-5-mini-2025-08-07                  | Function Calling | OpenAI         | gpt-5-mini-2025-08-07-FC                                    |
| GPT-5-nano-2025-08-07                  | Function Calling | OpenAI         | gpt-5-nano-2025-08-07-FC                                    |
| GPT-5.2-2025-12-11                     | Function Calling | OpenAI         | gpt-5.2-2025-12-11-FC                                       |
| Granite-20b-FunctionCalling            | Function Calling | Self-hosted 💻 | ibm-granite/granite-20b-functioncalling                     |
| Granite-3.1-8B-Instruct                | Function Calling | Self-hosted 💻 | ibm-granite/granite-3.1-8b-instruct                         |
| Granite-3.2-8B-Instruct                | Function Calling | Self-hosted 💻 | ibm-granite/granite-3.2-8b-instruct                         |
| Granite-4.0-350m                       | Function Calling | Self-hosted 💻 | ibm-granite/granite-4.0-350m                                |
| Grok-4-0709                            | Function Calling | xAI            | grok-4-0709-FC                                              |
| Grok-4-1-fast-non-reasoning            | Function Calling | xAI            | grok-4-1-fast-non-reasoning-FC                              |
| Grok-4-1-fast-reasoning                | Function Calling | xAI            | grok-4-1-fast-reasoning-FC                                  |
| Hammer2.1-{0.5b,1.5b,3b,7b}            | Function Calling | Self-hosted 💻 | MadeAgents/Hammer2.1-{0.5b,1.5b,3b,7b}                      |
| Llama-3.1-{8B,70B}-Instruct            | Function Calling | Self-hosted 💻 | meta-llama/Llama-3.1-{8B,70B}-Instruct-FC                   |
| Llama-3.1-Nemotron-Ultra-253B-v1       | Function Calling | NVIDIA         | nvidia/llama-3.1-nemotron-ultra-253b-v1                     |
| Llama-3.2-{1B,3B}-Instruct             | Function Calling | Self-hosted 💻 | meta-llama/Llama-3.2-{1B,3B}-Instruct-FC                    |
| Llama-3.3-70B-Instruct                 | Function Calling | Self-hosted 💻 | meta-llama/Llama-3.3-70B-Instruct-FC                        |
| Llama-4-Maverick-17B-128E-Instruct-FP8 | Function Calling | Novita AI      | meta-llama/llama-4-maverick-17b-128e-instruct-fp8-FC-novita |
| Llama-4-Maverick-17B-128E-Instruct-FP8 | Function Calling | Self-hosted 💻 | meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8-FC        |
| Llama-4-Scout-17B-16E-Instruct         | Function Calling | Novita AI      | meta-llama/llama-4-scout-17b-16e-instruct-FC-novita         |
| Llama-4-Scout-17B-16E-Instruct         | Function Calling | Self-hosted 💻 | meta-llama/Llama-4-Scout-17B-16E-Instruct-FC                |
| MiniCPM3-4B-FC                         | Function Calling | Self-hosted 💻 | openbmb/MiniCPM3-4B-FC                                      |
| mistral-large-2411                     | Function Calling | Mistral AI     | mistral-large-2411-FC                                       |
| Mistral-Medium-2505                    | Function Calling | Mistral AI     | mistral-medium-2505-FC                                      |
| Mistral-small-2506                     | Function Calling | Mistral AI     | mistral-small-2506-FC                                       |
| Moonshotai-Kimi-K2-Instruct            | Function Calling | MoonshotAI     | kimi-k2-0905-preview-FC                                     |
| Nanbeige3.5-Pro-Thinking               | Function Calling | Nanbeige       | Nanbeige3.5-Pro-Thinking-FC                                 |
| Nanbeige4-3B-Thinking-2511             | Function Calling | Self-hosted 💻 | Nanbeige/Nanbeige4-3B-Thinking-2511                         |
| o3-2025-04-16                          | Function Calling | OpenAI         | o3-2025-04-16-FC                                            |
| o4-mini-2025-04-16                     | Function Calling | OpenAI         | o4-mini-2025-04-16-FC                                       |
| Open-Mistral-Nemo-2407                 | Function Calling | Mistral AI     | open-mistral-nemo-2407-FC                                   |
| palmyra-x-004                          | Function Calling | Writer         | palmyra-x-004                                               |
| Phi-4-mini-instruct                    | Function Calling | Self-hosted 💻 | microsoft/Phi-4-mini-instruct-FC                            |
| Qwen/QwQ-32B                           | Function Calling | Novita AI      | qwen/qwq-32b-FC-novita                                      |
| Qwen3-{0.6B,1.7B,4B,8B,14B,32B}        | Function Calling | Qwen           | qwen3-{0.6b,1.7b,4b,8b,14b,32b}-FC                          |
| Qwen3-{0.6B,1.7B,8B,14B,32B}           | Function Calling | Self-hosted 💻 | Qwen/Qwen3-{0.6B,1.7B,8B,14B,32B}-FC                        |
| Qwen3-235B-A22B-Instruct-2507          | Function Calling | Qwen           | qwen3-235b-a22b-instruct-2507-FC                            |
| Qwen3-235B-A22B-Instruct-2507          | Function Calling | Self-hosted 💻 | Qwen/Qwen3-235B-A22B-Instruct-2507-FC                       |
| Qwen3-30B-A3B-Instruct-2507            | Function Calling | Qwen           | qwen3-30b-a3b-instruct-2507-FC                              |
| Qwen3-30B-A3B-Instruct-2507            | Function Calling | Self-hosted 💻 | Qwen/Qwen3-30B-A3B-Instruct-2507-FC                         |
| Qwen3-4B-Instruct-2507                 | Function Calling | Self-hosted 💻 | Qwen/Qwen3-4B-Instruct-2507-FC                              |
| Qwen3-4B-NoThink                       | Function Calling | Qwen           | qwen3-4b-nothink-FC                                         |
| Qwen3-4B-Think                         | Function Calling | Qwen           | qwen3-4b-think-FC                                           |
| QwQ-32B                                | Function Calling | Qwen           | qwq-32b-FC                                                  |
| ThinkAgent-1B                          | Function Calling | Self-hosted 💻 | ThinkAgents/ThinkAgent-1B                                   |
| xiaoming-14B                           | Function Calling | Mininglamp     | xiaoming-14B                                                |
| xLAM-2-1b-fc-r                         | Function Calling | Self-hosted 💻 | Salesforce/xLAM-2-1b-fc-r                                   |
| xLAM-2-32b-fc-r                        | Function Calling | Self-hosted 💻 | Salesforce/xLAM-2-32b-fc-r                                  |
| xLAM-2-3b-fc-r                         | Function Calling | Self-hosted 💻 | Salesforce/xLAM-2-3b-fc-r                                   |
| xLAM-2-70b-fc-r                        | Function Calling | Self-hosted 💻 | Salesforce/Llama-xLAM-2-70b-fc-r                            |
| xLAM-2-8b-fc-r                         | Function Calling | Self-hosted 💻 | Salesforce/Llama-xLAM-2-8b-fc-r                             |

---

## Additional Requirements for Certain Models

- **Gemini Models:**
  For `Gemini` models, we use the Google AI Studio API for inference. Ensure you have set the `GOOGLE_API_KEY` in your `.env` file.

- **Nova Models (AWS Bedrock):**
  For `Nova` models, set your `AWS_SSO_PROFILE_NAME` in your `.env` file after completing the [AWS SSO token provider setup](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html). Make sure the necessary AWS Bedrock permissions are granted in the `us-east-1` region.

---

For more details and a summary of feature support across different models, see the [Berkeley Function Calling Leaderboard blog post](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html#prompt).
