# Table of Supported Models

Below is a comprehensive table of models supported for running leaderboard evaluations. Every model is evaluated through its native Function Calling (FC) interface. Models marked with `💻` are intended to be hosted locally (using vllm or sglang), while models without the `💻` icon are accessed via API calls. To quickly see all available models, you can also run the `bfcl models` command.

| Base Model                             | Provider      | Model ID on BFCL                                  |
| -------------------------------------- | ------------- | ------------------------------------------------- |
| Amazon-Nova-2-Lite-v1:0                | Amazon        | nova-2-lite-v1.0                                  |
| Amazon-Nova-Micro-v1:0                 | Amazon        | nova-micro-v1.0                                   |
| Amazon-Nova-Pro-v1:0                   | Amazon        | nova-pro-v1.0                                     |
| Claude-Haiku-4-5-20251001              | Anthropic     | claude-haiku-4-5-20251001                         |
| Claude-Opus-5                          | Anthropic     | claude-opus-5                                     |
| Claude-Sonnet-5                        | Anthropic     | claude-sonnet-5                                   |
| Command A+                             | Self-hosted 💻 | CohereLabs/command-a-plus-05-2026-bf16            |
| DeepSeek-V4-Flash                      | DeepSeek      | DeepSeek-V4-Flash                                 |
| DeepSeek-V4-Pro                        | DeepSeek      | DeepSeek-V4-Pro                                   |
| FunctionGemma-270m-it                  | Self-hosted 💻 | google/functiongemma-270m-it                      |
| Gemini-3.1-Flash-Lite-Preview          | Google        | gemini-3.1-flash-lite-preview                     |
| Gemini-3.1-Pro-Preview                 | Google        | gemini-3.1-pro-preview                            |
| Gemini-3.5-Flash                       | Google        | gemini-3.5-flash                                  |
| Gemma-4-26B-A4B-it                     | Self-hosted 💻 | google/gemma-4-26B-A4B-it                         |
| Gemma-4-31B-it                         | Self-hosted 💻 | google/gemma-4-31B-it                             |
| Gemma-4-E2B-it                         | Self-hosted 💻 | google/gemma-4-E2B-it                             |
| Gemma-4-E4B-it                         | Self-hosted 💻 | google/gemma-4-E4B-it                             |
| GLM-4.6V                               | Self-hosted 💻 | zai-org/GLM-4.6V                                  |
| GLM-4.6V-Flash                         | Self-hosted 💻 | zai-org/GLM-4.6V-Flash                            |
| GLM-5.2 (thinking)                     | Zhipu AI      | glm-5.2                                           |
| GLM-5v-Turbo                           | Zhipu AI      | glm-5v-turbo                                      |
| GPT-5.6-Luna                           | OpenAI        | gpt-5.6-luna                                      |
| GPT-5.6-Sol                            | OpenAI        | gpt-5.6-sol                                       |
| GPT-5.6-Terra                          | OpenAI        | gpt-5.6-terra                                     |
| gpt-oss-120b                           | Self-hosted 💻 | openai/gpt-oss-120b                               |
| gpt-oss-20b                            | Self-hosted 💻 | openai/gpt-oss-20b                                |
| Granite-3.1-8B-Instruct                | Self-hosted 💻 | ibm-granite/granite-3.1-8b-instruct               |
| Granite-3.2-8B-Instruct                | Self-hosted 💻 | ibm-granite/granite-3.2-8b-instruct               |
| Granite-4.0-350m                       | Self-hosted 💻 | ibm-granite/granite-4.0-350m                      |
| Grok-4.5                               | xAI           | grok-4.5                                          |
| Hammer2.1-0.5b                         | Self-hosted 💻 | MadeAgents/Hammer2.1-0.5b                         |
| Hammer2.1-1.5b                         | Self-hosted 💻 | MadeAgents/Hammer2.1-1.5b                         |
| Hammer2.1-3b                           | Self-hosted 💻 | MadeAgents/Hammer2.1-3b                           |
| Hammer2.1-7b                           | Self-hosted 💻 | MadeAgents/Hammer2.1-7b                           |
| Hy3                                    | Self-hosted 💻 | tencent/Hy3                                       |
| Inkling                                | Self-hosted 💻 | thinkingmachines/Inkling                          |
| Inkling-Small                          | Self-hosted 💻 | thinkingmachines/Inkling-Small                    |
| Kimi-K3                                | MoonshotAI    | kimi-k3                                           |
| Ling-2.6-1T                            | inclusionAI   | Ling-2.6-1T                                       |
| Ling-2.6-flash                         | Self-hosted 💻 | inclusionAI/Ling-2.6-flash                        |
| Llama-4-Maverick-17B-128E-Instruct-FP8 | Self-hosted 💻 | meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8 |
| Llama-4-Scout-17B-16E-Instruct         | Self-hosted 💻 | meta-llama/Llama-4-Scout-17B-16E-Instruct         |
| MiMo-V2.5                              | Self-hosted 💻 | XiaomiMiMo/MiMo-V2.5                              |
| MiMo-V2.5-Pro                          | Xiaomi        | mimo-v2.5-pro                                     |
| MiniCPM5-1B                            | Self-hosted 💻 | openbmb/MiniCPM5-1B                               |
| MiniMax-M3                             | Self-hosted 💻 | MiniMaxAI/MiniMax-M3                              |
| Mistral-Large-3                        | Mistral AI    | mistral-large-2512                                |
| Mistral-Medium-3.5-128B                | Self-hosted 💻 | mistralai/Mistral-Medium-3.5-128B                 |
| Mistral-Small-4-119B-2603              | Self-hosted 💻 | mistralai/Mistral-Small-4-119B-2603               |
| Muse-Spark-1.1                         | Meta          | muse-spark-1.1                                    |
| Nanbeige3.5-Pro-Thinking               | Nanbeige      | Nanbeige3.5-Pro-Thinking                          |
| Nanbeige4.2-3B                         | Self-hosted 💻 | Nanbeige/Nanbeige4.2-3B                           |
| palmyra-x5                             | Writer        | palmyra-x5                                        |
| Phi-4-mini-instruct                    | Self-hosted 💻 | microsoft/Phi-4-mini-instruct                     |
| Qwen3.5-0.8B                           | Self-hosted 💻 | Qwen/Qwen3.5-0.8B                                 |
| Qwen3.5-122B-A10B                      | Self-hosted 💻 | Qwen/Qwen3.5-122B-A10B                            |
| Qwen3.5-2B                             | Self-hosted 💻 | Qwen/Qwen3.5-2B                                   |
| Qwen3.5-397B-A17B                      | Self-hosted 💻 | Qwen/Qwen3.5-397B-A17B                            |
| Qwen3.5-4B                             | Self-hosted 💻 | Qwen/Qwen3.5-4B                                   |
| Qwen3.5-9B                             | Self-hosted 💻 | Qwen/Qwen3.5-9B                                   |
| Qwen3.6-27B                            | Self-hosted 💻 | Qwen/Qwen3.6-27B                                  |
| Qwen3.6-35B-A3B                        | Self-hosted 💻 | Qwen/Qwen3.6-35B-A3B                              |
| Seed-OSS-36B-Instruct                  | Self-hosted 💻 | ByteDance-Seed/Seed-OSS-36B-Instruct              |
| Step-3.7-Flash                         | Self-hosted 💻 | stepfun-ai/Step-3.7-Flash                         |
| ToolACE-2.5-Llama-3.1-8B               | Self-hosted 💻 | Team-ACE/ToolACE-2.5-Llama-3.1-8B                 |
| xLAM-2-1b-fc-r                         | Self-hosted 💻 | Salesforce/xLAM-2-1b-fc-r                         |
| xLAM-2-32b-fc-r                        | Self-hosted 💻 | Salesforce/xLAM-2-32b-fc-r                        |
| xLAM-2-3b-fc-r                         | Self-hosted 💻 | Salesforce/xLAM-2-3b-fc-r                         |
| xLAM-2-70b-fc-r                        | Self-hosted 💻 | Salesforce/Llama-xLAM-2-70b-fc-r                  |
| xLAM-2-8b-fc-r                         | Self-hosted 💻 | Salesforce/Llama-xLAM-2-8b-fc-r                   |

---

## Additional Requirements for Certain Models

- **Gemini Models:**
  For `Gemini` models, we use the Google AI Studio API for inference. Ensure you have set the `GOOGLE_API_KEY` in your `.env` file.

- **Nova Models (AWS Bedrock):**
  For `Nova` models, set your `AWS_SSO_PROFILE_NAME` in your `.env` file after completing the [AWS SSO token provider setup](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html). Make sure the necessary AWS Bedrock permissions are granted in the `us-east-1` region.

---

For more details and a summary of feature support across different models, see the [Berkeley Function Calling Leaderboard blog post](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html#prompt).
