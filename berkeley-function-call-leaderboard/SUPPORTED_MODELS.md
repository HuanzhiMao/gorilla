# Table of Supported Models

Below is a comprehensive table of models supported for running leaderboard evaluations. Every model is evaluated through its native Function Calling (FC) interface. Models marked with `💻` are intended to be hosted locally (using vllm or sglang), while models without the `💻` icon are accessed via API calls. To quickly see all available models, you can also run the `bfcl models` command.

| Base Model                             | Provider      | Model ID on BFCL                                     |
| -------------------------------------- | ------------- | ---------------------------------------------------- |
| Amazon-Nova-2-Lite-v1:0                | Amazon        | nova-2-lite-v1.0                                     |
| Amazon-Nova-Micro-v1:0                 | Amazon        | nova-micro-v1.0                                      |
| Amazon-Nova-Pro-v1:0                   | Amazon        | nova-pro-v1.0                                        |
| Claude-Haiku-4-5-20251001              | Anthropic     | claude-haiku-4-5-20251001-FC                         |
| Claude-Opus-4-7                        | Anthropic     | claude-opus-4-7-FC                                   |
| Claude-Sonnet-4-6                      | Anthropic     | claude-sonnet-4-6-FC                                 |
| Command A                              | Cohere        | CohereLabs/c4ai-command-a-03-2025                    |
| Command A Reasoning                    | Cohere        | CohereLabs/command-a-reasoning-08-2025               |
| Command A Vision                       | Cohere        | CohereLabs/command-a-vision-07-2025                  |
| DeepSeek-V3.2                          | DeepSeek      | DeepSeek-V3.2-FC                                     |
| DeepSeek-V3.2 (self-hosted)            | Self-hosted 💻 | deepseek-ai/DeepSeek-V3.2-FC                         |
| FunctionGemma-270m-it                  | Self-hosted 💻 | google/functiongemma-270m-it-FC                      |
| Gemini-3-Flash-Preview                 | Google        | gemini-3-flash-preview-FC                            |
| Gemini-3.1-Flash-Lite-Preview          | Google        | gemini-3.1-flash-lite-preview-FC                     |
| Gemini-3.1-Pro-Preview                 | Google        | gemini-3.1-pro-preview-FC                            |
| Gemma-4-26B-A4B-it                     | Self-hosted 💻 | google/gemma-4-26B-A4B-it-FC                         |
| Gemma-4-31B-it                         | Self-hosted 💻 | google/gemma-4-31B-it-FC                             |
| Gemma-4-E2B-it                         | Self-hosted 💻 | google/gemma-4-E2B-it-FC                             |
| Gemma-4-E4B-it                         | Self-hosted 💻 | google/gemma-4-E4B-it-FC                             |
| GLM-4.6v                               | Zhipu AI      | glm-4.6v-FC                                          |
| GLM-4.6v-Flash                         | Zhipu AI      | glm-4.6v-flash-FC                                    |
| GLM-5.1 (thinking)                     | Zhipu AI      | glm-5.1-FC                                           |
| GLM-5v-Turbo                           | Zhipu AI      | glm-5v-turbo-FC                                      |
| Gorilla-OpenFunctions-v2               | Gorilla LLM   | gorilla-openfunctions-v2                             |
| GPT-4o-2024-11-20                      | OpenAI        | gpt-4o-2024-11-20-FC                                 |
| GPT-4o-mini-2024-07-18                 | OpenAI        | gpt-4o-mini-2024-07-18-FC                            |
| GPT-5.2-2025-12-11                     | OpenAI        | gpt-5.2-2025-12-11-FC                                |
| GPT-5.4-2026-03-05                     | OpenAI        | gpt-5.4-2026-03-05-FC                                |
| GPT-5.4-mini-2026-03-17                | OpenAI        | gpt-5.4-mini-2026-03-17-FC                           |
| GPT-5.4-nano-2026-03-17                | OpenAI        | gpt-5.4-nano-2026-03-17-FC                           |
| Granite-3.1-8B-Instruct                | Self-hosted 💻 | ibm-granite/granite-3.1-8b-instruct                  |
| Granite-3.2-8B-Instruct                | Self-hosted 💻 | ibm-granite/granite-3.2-8b-instruct                  |
| Granite-4.0-350m                       | Self-hosted 💻 | ibm-granite/granite-4.0-350m                         |
| Grok-4-1-fast-non-reasoning            | xAI           | grok-4-1-fast-non-reasoning-FC                       |
| Grok-4.20-Beta-0309-Reasoning          | xAI           | grok-4.20-beta-0309-reasoning-FC                     |
| Grok-4.3                               | xAI           | grok-4.3-FC                                          |
| Hammer2.1-0.5b                         | Self-hosted 💻 | MadeAgents/Hammer2.1-0.5b                            |
| Hammer2.1-1.5b                         | Self-hosted 💻 | MadeAgents/Hammer2.1-1.5b                            |
| Hammer2.1-3b                           | Self-hosted 💻 | MadeAgents/Hammer2.1-3b                              |
| Hammer2.1-7b                           | Self-hosted 💻 | MadeAgents/Hammer2.1-7b                              |
| Kimi-K2.5                              | MoonshotAI    | kimi-k2.5-FC                                         |
| Llama-3.1-Nemotron-Ultra-253B-v1       | NVIDIA        | nvidia/llama-3.1-nemotron-ultra-253b-v1              |
| Llama-3.2-1B-Instruct                  | Self-hosted 💻 | meta-llama/Llama-3.2-1B-Instruct-FC                  |
| Llama-3.2-3B-Instruct                  | Self-hosted 💻 | meta-llama/Llama-3.2-3B-Instruct-FC                  |
| Llama-4-Maverick-17B-128E-Instruct-FP8 | Self-hosted 💻 | meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8-FC |
| Llama-4-Scout-17B-16E-Instruct         | Self-hosted 💻 | meta-llama/Llama-4-Scout-17B-16E-Instruct-FC         |
| Mistral-Large-3-675B-Instruct-2512     | Self-hosted 💻 | mistralai/Mistral-Large-3-675B-Instruct-2512-FC      |
| Mistral-Medium-2508                    | Mistral AI    | mistral-medium-2508-FC                               |
| Mistral-small-2506                     | Mistral AI    | mistral-small-2506-FC                                |
| Mistral-Small-4-119B-2603              | Self-hosted 💻 | mistralai/Mistral-Small-4-119B-2603                  |
| Nanbeige3.5-Pro-Thinking               | Nanbeige      | Nanbeige3.5-Pro-Thinking-FC                          |
| o3-2025-04-16                          | OpenAI        | o3-2025-04-16-FC                                     |
| o4-mini-2025-04-16                     | OpenAI        | o4-mini-2025-04-16-FC                                |
| palmyra-x5                             | Writer        | palmyra-x5-FC                                        |
| Phi-4-mini-instruct                    | Self-hosted 💻 | microsoft/Phi-4-mini-instruct-FC                     |
| Qwen3-4B-NoThink                       | Qwen          | qwen3-4b-nothink-FC                                  |
| Qwen3-4B-Think                         | Qwen          | qwen3-4b-think-FC                                    |
| Qwen3.5-0.8B                           | Self-hosted 💻 | Qwen/Qwen3.5-0.8B-FC                                 |
| Qwen3.5-122B-A10B                      | Self-hosted 💻 | Qwen/Qwen3.5-122B-A10B-FC                            |
| Qwen3.5-27B                            | Self-hosted 💻 | Qwen/Qwen3.5-27B-FC                                  |
| Qwen3.5-2B                             | Self-hosted 💻 | Qwen/Qwen3.5-2B-FC                                   |
| Qwen3.5-35B-A3B                        | Self-hosted 💻 | Qwen/Qwen3.5-35B-A3B-FC                              |
| Qwen3.5-397B-A17B                      | Self-hosted 💻 | Qwen/Qwen3.5-397B-A17B-FC                            |
| Qwen3.5-4B                             | Self-hosted 💻 | Qwen/Qwen3.5-4B-FC                                   |
| Qwen3.5-9B                             | Self-hosted 💻 | Qwen/Qwen3.5-9B-FC                                   |
| xLAM-2-1b-fc-r                         | Self-hosted 💻 | Salesforce/xLAM-2-1b-fc-r                            |
| xLAM-2-32b-fc-r                        | Self-hosted 💻 | Salesforce/xLAM-2-32b-fc-r                           |
| xLAM-2-3b-fc-r                         | Self-hosted 💻 | Salesforce/xLAM-2-3b-fc-r                            |
| xLAM-2-70b-fc-r                        | Self-hosted 💻 | Salesforce/Llama-xLAM-2-70b-fc-r                     |
| xLAM-2-8b-fc-r                         | Self-hosted 💻 | Salesforce/Llama-xLAM-2-8b-fc-r                      |

---

## Additional Requirements for Certain Models

- **Gemini Models:**
  For `Gemini` models, we use the Google AI Studio API for inference. Ensure you have set the `GOOGLE_API_KEY` in your `.env` file.

- **Nova Models (AWS Bedrock):**
  For `Nova` models, set your `AWS_SSO_PROFILE_NAME` in your `.env` file after completing the [AWS SSO token provider setup](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html). Make sure the necessary AWS Bedrock permissions are granted in the `us-east-1` region.

---

For more details and a summary of feature support across different models, see the [Berkeley Function Calling Leaderboard blog post](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html#prompt).
