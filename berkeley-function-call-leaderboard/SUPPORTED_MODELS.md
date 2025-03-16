# Table of Supported Models

Below is a comprehensive table of models supported for running leaderboard evaluations. Each model entry indicates whether it supports native Function Calling (FC) or requires a special prompt format to generate function calls. Models marked with `💻` are intended to be hosted locally (using vllm or sglang), while models without the `💻` icon are accessed via API calls. To quickly see all available models, you can also run the `bfcl models` command.

**Note:**  

- **Function Calling (FC)** models directly support the function calling schema as documented by their respective providers.
- **Prompt** models do not natively support function calling. For these, we supply a consistent system message prompting the model to produce function calls in the desired format.

<div class="model-table">
<table>
    <tr>
        <th>Base Model</th>
        <th>Model Version</th>
        <th>Type</th>
        <th>Provider</th>
        <th>Model Name in BFCL</th>
    </tr>
    <tr class="single-row">
        <td>Gorilla</td>
        <td>v2</td>
        <td>Function Calling</td>
        <td>Gorilla LLM</td>
        <td>gorilla-openfunctions-v2</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Claude</td>
        <td>Opus 3</td>
        <td>Function Calling</td>
        <td>Anthropic</td>
        <td>claude-3-opus-20240229-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Claude</td>
        <td>Opus 3</td>
        <td>Prompt</td>
        <td>Anthropic</td>
        <td>claude-3-opus-20240229</td>
    </tr>
    <tr class="model-row hidden">
        <td>Claude</td>
        <td>Haiku 3.5</td>
        <td>Function Calling</td>
        <td>Anthropic</td>
        <td>claude-3-5-haiku-20241022-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Claude</td>
        <td>Haiku 3.5</td>
        <td>Prompt</td>
        <td>Anthropic</td>
        <td>claude-3-5-haiku-20241022</td>
    </tr>
    <tr class="model-row hidden">
        <td>Claude</td>
        <td>Sonnet 3.5</td>
        <td>Function Calling</td>
        <td>Anthropic</td>
        <td>claude-3-5-sonnet-20241022-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Claude</td>
        <td>Sonnet 3.5</td>
        <td>Prompt</td>
        <td>Anthropic</td>
        <td>claude-3-5-sonnet-20241022</td>
    </tr>
    <tr class="model-row hidden">
        <td>Claude</td>
        <td>Sonnet 3.7</td>
        <td>Function Calling</td>
        <td>Anthropic</td>
        <td>claude-3-7-sonnet-20250219-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Claude</td>
        <td>Sonnet 3.7</td>
        <td>Prompt</td>
        <td>Anthropic</td>
        <td>claude-3-7-sonnet-20250219</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>DeepSeek</td>
        <td>R1</td>
        <td>Prompt</td>
        <td>DeepSeek</td>
        <td>DeepSeek-R1</td>
    </tr>
    <tr class="model-row hidden">
        <td>DeepSeek</td>
        <td>V3</td>
        <td>Function Calling</td>
        <td>DeepSeek</td>
        <td>DeepSeek-V3-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>DeepSeek</td>
        <td>R1</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>deepseek-ai/DeepSeek-R1</td>
    </tr>
    <tr class="model-row hidden">
        <td>DeepSeek</td>
        <td>V2.5</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>deepseek-ai/DeepSeek-V2.5</td>
    </tr>
    <tr class="model-row hidden">
        <td>DeepSeek</td>
        <td>V2-Chat-0628</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>deepseek-ai/DeepSeek-V2-Chat-0628</td>
    </tr>
    <tr class="model-row hidden">
        <td>DeepSeek</td>
        <td>V2-Lite-Chat</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>deepseek-ai/DeepSeek-V2-Lite-Chat</td>
    </tr>
    <tr class="model-row hidden">
        <td>DeepSeek</td>
        <td>Coder-V2-Instruct-0724</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>deepseek-ai/DeepSeek-Coder-V2-Instruct-0724</td>
    </tr>
    <tr class="model-row hidden">
        <td>DeepSeek</td>
        <td>Coder-V2-Lite-Instruct</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>ChatGPT</td>
        <td>3.5 Turbo</td>
        <td>Function Calling</td>
        <td>OpenAI</td>
        <td>gpt-3.5-turbo-0125-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>3.5 Turbo</td>
        <td>Prompt</td>
        <td>OpenAI</td>
        <td>gpt-3.5-turbo-0125</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>4 Turbo</td>
        <td>Function Calling</td>
        <td>OpenAI</td>
        <td>gpt-4-turbo-2024-04-09-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>4 Turbo</td>
        <td>Prompt</td>
        <td>OpenAI</td>
        <td>gpt-4-turbo-2024-04-09</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>4o</td>
        <td>Function Calling</td>
        <td>OpenAI</td>
        <td>gpt-4o-2024-11-20-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>4o</td>
        <td>Prompt</td>
        <td>OpenAI</td>
        <td>gpt-4o-2024-11-20</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>4o mini</td>
        <td>Function Calling</td>
        <td>OpenAI</td>
        <td>gpt-4o-mini-2024-07-18-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>4o mini</td>
        <td>Prompt</td>
        <td>OpenAI</td>
        <td>gpt-4o-mini-2024-07-18</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>4.5 preview</td>
        <td>Function Calling</td>
        <td>OpenAI</td>
        <td>gpt-4.5-preview-2025-02-27-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>4.5 preview</td>
        <td>Prompt</td>
        <td>OpenAI</td>
        <td>gpt-4.5-preview-2025-02-27</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>o1</td>
        <td>Function Calling</td>
        <td>OpenAI</td>
        <td>o1-2024-12-17-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>o1</td>
        <td>Prompt</td>
        <td>OpenAI</td>
        <td>o1-2024-12-17</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>o3 mini</td>
        <td>Function Calling</td>
        <td>OpenAI</td>
        <td>o3-mini-2025-01-31-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>ChatGPT</td>
        <td>o3 mini</td>
        <td>Prompt</td>
        <td>OpenAI</td>
        <td>o3-mini-2025-01-31</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Gemini</td>
        <td>Pro 1.0</td>
        <td>Function Calling</td>
        <td>Google</td>
        <td>gemini-1.0-pro-002-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 1.0</td>
        <td>Prompt</td>
        <td>Google</td>
        <td>gemini-1.0-pro-002</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 1.5</td>
        <td>Function Calling</td>
        <td>Google</td>
        <td>gemini-1.5-pro-001-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 1.5</td>
        <td>Function Calling</td>
        <td>Google</td>
        <td>gemini-1.5-pro-002-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 1.5</td>
        <td>Prompt</td>
        <td>Google</td>
        <td>gemini-1.5-pro-001</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 1.5</td>
        <td>Prompt</td>
        <td>Google</td>
        <td>gemini-1.5-pro-002</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 1.5 Flash</td>
        <td>Function Calling</td>
        <td>Google</td>
        <td>gemini-1.5-flash-001-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 1.5 Flash</td>
        <td>Function Calling</td>
        <td>Google</td>
        <td>gemini-1.5-flash-002-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 1.5 Flash</td>
        <td>Prompt</td>
        <td>Google</td>
        <td>gemini-1.5-flash-001</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 1.5 Flash</td>
        <td>Prompt</td>
        <td>Google</td>
        <td>gemini-1.5-flash-002</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 2.0 Pro Experimental</td>
        <td>Function Calling</td>
        <td>Google</td>
        <td>gemini-2.0-pro-exp-02-05-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 2.0 Pro Experimental</td>
        <td>Prompt</td>
        <td>Google</td>
        <td>gemini-2.0-pro-exp-02-05</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 2.0 Flash</td>
        <td>Function Calling</td>
        <td>Google</td>
        <td>gemini-2.0-flash-001-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 2.0 Flash</td>
        <td>Prompt</td>
        <td>Google</td>
        <td>gemini-2.0-flash-001</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 2.0 Flash Lite Preview</td>
        <td>Function Calling</td>
        <td>Google</td>
        <td>gemini-2.0-flash-lite-preview-02-05-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemini</td>
        <td>Pro 2.0 Flash Lite Preview</td>
        <td>Prompt</td>
        <td>Google</td>
        <td>gemini-2.0-flash-lite-preview-02-05</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Mixtral</td>
        <td>Open 8x7b</td>
        <td>Prompt</td>
        <td>Mistral</td>
        <td>open-mixtral-8x7b</td>
    </tr>
    <tr class="model-row hidden">
        <td>Mixtral</td>
        <td>Open 8x22b</td>
        <td>Prompt</td>
        <td>Mistral</td>
        <td>open-mixtral-8x22b</td>
    </tr>
    <tr class="model-row hidden">
        <td>Mixtral</td>
        <td>Open 8x22b</td>
        <td>Function Calling</td>
        <td>Mistral</td>
        <td>open-mixtral-8x22b-FC</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Mistral</td>
        <td>Open Nemo</td>
        <td>Prompt</td>
        <td>Mistral</td>
        <td>open-mistral-nemo-2407</td>
    </tr>
    <tr class="model-row hidden">
        <td>Mistral</td>
        <td>Open Nemo</td>
        <td>Function Calling</td>
        <td>Mistral</td>
        <td>open-mistral-nemo-2407-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Mistral</td>
        <td>Large</td>
        <td>Function Calling</td>
        <td>Mistral</td>
        <td>mistral-large-2407-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Mistral</td>
        <td>Large</td>
        <td>Prompt</td>
        <td>Mistral</td>
        <td>mistral-large-2407</td>
    </tr>
    <tr class="model-row hidden">
        <td>Mistral</td>
        <td>Medium</td>
        <td>Prompt</td>
        <td>Mistral</td>
        <td>mistral-medium-2312</td>
    </tr>
    <tr class="model-row hidden">
        <td>Mistral</td>
        <td>Small</td>
        <td>Function Calling</td>
        <td>Mistral</td>
        <td>mistral-small-2402-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Mistral</td>
        <td>Small</td>
        <td>Prompt</td>
        <td>Mistral</td>
        <td>mistral-small-2402</td>
    </tr>
    <tr class="model-row hidden">
        <td>Mistral</td>
        <td>Tiny</td>
        <td>Prompt</td>
        <td>Mistral</td>
        <td>mistral-tiny-2312</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Nova</td>
        <td>Pro v1.0</td>
        <td>Function Calling</td>
        <td>Amazon</td>
        <td>nova-pro-v1.0</td>
    </tr>
    <tr class="model-row hidden">
        <td>Nova</td>
        <td>Lite v1.0</td>
        <td>Function Calling</td>
        <td>Amazon</td>
        <td>nova-lite-v1.0</td>
    </tr>
    <tr class="model-row hidden">
        <td>Nova</td>
        <td>Macro v1.0</td>
        <td>Function Calling</td>
        <td>Amazon</td>
        <td>nova-macro-v1.0</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Command R</td>
        <td>Plus</td>
        <td>Function Calling</td>
        <td>CohereForAI</td>
        <td>command-r-plus-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Command R</td>
        <td>7B</td>
        <td>Function Calling</td>
        <td>CohereForAI</td>
        <td>command-r7b-12-2024-FC</td>
    </tr>
    <tr class="single-row">
        <td>Dbrx</td>
        <td>Instruct</td>
        <td>Prompt</td>
        <td>Databricks</td>
        <td>databrick-dbrx-instruct</td>
    </tr>
    <tr class="single-row">
        <td>Firefunction</td>
        <td>v1</td>
        <td>Function Calling</td>
        <td>FireworksAI</td>
        <td>firefunction-v1-FC</td>
    </tr>
    <tr class="single-row">
        <td>Yi</td>
        <td>?</td>
        <td>Function Calling</td>
        <td>?</td>
        <td>yi-large-fc</td>
    </tr>
    <tr class="single-row">
        <td>Grok</td>
        <td>Beta</td>
        <td>Function Calling</td>
        <td>xAI</td>
        <td>grok-beta</td>
    </tr>
    <tr class="single-row">
        <td>Nemotron</td>
        <td>4</td>
        <td>Prompt</td>
        <td>Nvidia</td>
        <td>nvidia/nemotron-4-340b-instruct</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Functionary</td>
        <td>Small</td>
        <td>Function Calling</td>
        <td>Meetkai</td>
        <td>meetkai/functionary-small-v3.1-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Functionary</td>
        <td>Medium</td>
        <td>Function Calling</td>
        <td>Meetkai</td>
        <td>meetkai/functionary-medium-v3.1-FC</td>
    </tr>
    <tr class="single-row">
        <td>Raven</td>
        <td>v2</td>
        <td>Function Calling</td>
        <td>Nexusflow</td>
        <td>Nexusflow-Raven-v2</td>
    </tr>
    <tr class="single-row">
        <td>"Palmyra"</td>
        <td>"x-004"</td>
        <td>Function Calling</td>
        <td>"Palmyra AI"</td>
        <td>"palmyra-x-004"</td>
    </tr>
    <tr class="single-row">
        <td>"Snowflake Arctic"</td>
        <td>?</td>
        <td>Prompt</td>
        <td>"Snowflake"</td>
        <td>"snowflake/arctic"</td>
    </tr>
    <tr class="single-row">
        <td>"GoGoAgent"</td>
        <td>?</td>
        <td>Prompt</td>
        <td>"BitAgent"</td>
        <td>"BitAgent/GoGoAgent"</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Gemma</td>
        <td>2-2B</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>google/gemma-2-2b-it</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemma</td>
        <td>2-9B</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>google/gemma-2-9b-it</td>
    </tr>
    <tr class="model-row hidden">
        <td>Gemma</td>
        <td>2-27B</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>google/gemma-2-27b-it</td>
    </tr>
    <tr class="single-row">
        <td>Ministral</td>
        <td>8B-Instruct-2410</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>mistralai/Ministral-8B-Instruct-2410</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Meta-Llama 3</td>
        <td>8B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>meta-llama/Meta-Llama-3-8B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Meta-Llama 3</td>
        <td>70B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>meta-llama/Meta-Llama-3-70B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Meta-Llama 3.1</td>
        <td>8B-Instruct-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>meta-llama/Llama-3.1-8B-Instruct-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Meta-Llama 3.1</td>
        <td>70B-Instruct-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>meta-llama/Llama-3.1-70B-Instruct-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Meta-Llama 3.1</td>
        <td>8B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>meta-llama/Llama-3.1-8B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Meta-Llama 3.1</td>
        <td>70B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>meta-llama/Llama-3.1-70B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Meta-Llama 3.2</td>
        <td>1B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>meta-llama/Llama-3.2-1B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Meta-Llama 3.2</td>
        <td>3B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>meta-llama/Llama-3.2-3B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Meta-Llama 3.3</td>
        <td>70B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>meta-llama/Llama-3.3-70B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Meta-Llama 3.3</td>
        <td>70B-Instruct-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>meta-llama/Llama-3.3-70B-Instruct-FC</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Qwen</td>
        <td>2.5-0.5B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-0.5B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-1.5B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-1.5B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-3B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-3B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-7B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-7B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-14B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-14B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-32B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-32B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-72B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-72B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-0.5B-Instruct-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-0.5B-Instruct-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-1.5B-Instruct-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-1.5B-Instruct-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-3B-Instruct-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-3B-Instruct-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-7B-Instruct-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-7B-Instruct-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-14B-Instruct-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-14B-Instruct-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-32B-Instruct-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-32B-Instruct-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2.5-72B-Instruct-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2.5-72B-Instruct-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2-1.5B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2-1.5B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Qwen</td>
        <td>2-7B-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>Qwen/Qwen2-7B-Instruct</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Salesforce xLAM</td>
        <td>1b-fc-r</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Salesforce/xLAM-1b-fc-r</td>
    </tr>
    <tr class="model-row hidden">
        <td>Salesforce xLAM</td>
        <td>7b-fc-r</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Salesforce/xLAM-7b-fc-r</td>
    </tr>
    <tr class="model-row hidden">
        <td>Salesforce xLAM</td>
        <td>7b-r</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Salesforce/xLAM-7b-r</td>
    </tr>
    <tr class="model-row hidden">
        <td>Salesforce xLAM</td>
        <td>8x7b-r</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Salesforce/xLAM-8x7b-r</td>
    </tr>
    <tr class="model-row hidden">
        <td>Salesforce xLAM</td>
        <td>8x22b-r</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Salesforce/xLAM-8x22b-r</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Phi</td>
        <td>3.5-mini-instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>microsoft/Phi-3.5-mini-instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Phi</td>
        <td>3-medium-4k</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>microsoft/Phi-3-medium-4k-instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Phi</td>
        <td>3-medium-128k</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>microsoft/Phi-3-medium-128k-instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Phi</td>
        <td>3-small-8k</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>microsoft/Phi-3-small-8k-instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Phi</td>
        <td>3-small-128k</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>microsoft/Phi-3-small-128k-instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Phi</td>
        <td>3-mini-4k</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>microsoft/Phi-3-mini-4k-instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Phi</td>
        <td>3-mini-128k</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>microsoft/Phi-3-mini-128k-instruct</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Hermes</td>
        <td>2-Pro-Llama-3</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>NousResearch/Hermes-2-Pro-Llama-3-8B</td>
    </tr>
    <tr class="model-row hidden">
        <td>Hermes</td>
        <td>2-Pro-Llama-3</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>NousResearch/Hermes-2-Pro-Llama-3-70B</td>
    </tr>
    <tr class="model-row hidden">
        <td>Hermes</td>
        <td>2-Pro-Mistral-7B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>NousResearch/Hermes-2-Pro-Mistral-7B</td>
    </tr>
    <tr class="model-row hidden">
        <td>Hermes</td>
        <td>2-Theta-Llama-3</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>NousResearch/Hermes-2-Theta-Llama-3-8B</td>
    </tr>
    <tr class="model-row hidden">
        <td>Hermes</td>
        <td>2-Theta-Llama-3</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>NousResearch/Hermes-2-Theta-Llama-3-70B</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Hammer</td>
        <td>2.1-7B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>MadeAgents/Hammer2.1-7b</td>
    </tr>
    <tr class="model-row hidden">
        <td>Hammer</td>
        <td>2.1-3B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>MadeAgents/Hammer2.1-3b</td>
    </tr>
    <tr class="model-row hidden">
        <td>Hammer</td>
        <td>2.11.53B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>MadeAgents/Hammer2.1-1.5b</td>
    </tr>
    <tr class="model-row hidden">
        <td>Hammer</td>
        <td>2.1-0.5B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>MadeAgents/Hammer2.1-0.5b</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>MiniCPM</td>
        <td>3-4B-FC</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>openbmb/MiniCPM3-4B-FC</td>
    </tr>
    <tr class="model-row hidden">
        <td>MiniCPM</td>
        <td>3-4B</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>openbmb/MiniCPM3-4B</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Watt Tool</td>
        <td>8B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>watt-ai/watt-tool-8B</td>
    </tr>
    <tr class="model-row hidden">
        <td>Watt Tool</td>
        <td>70B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>watt-ai/watt-tool-70B</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>Falcon3</td>
        <td>1B-Instruct</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>tiiuae/Falcon3-1B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Falcon3</td>
        <td>3B-Instruct</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>tiiuae/Falcon3-3B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Falcon3</td>
        <td>7B-Instruct</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>tiiuae/Falcon3-7B-Instruct</td>
    </tr>
    <tr class="model-row hidden">
        <td>Falcon3</td>
        <td>10B-Instruct</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>tiiuae/Falcon3-10B-Instruct</td>
    </tr>
    <tr class="expandable-row" onclick="toggleModelRows(this)">
        <td>CoALM</td>
        <td>8B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>uiuc-convai/CoALM-8B</td>
    </tr>
    <tr class="model-row hidden">
        <td>CoALM</td>
        <td>70B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>uiuc-convai/CoALM-70B</td>
    </tr>
    <tr class="model-row hidden">
        <td>CoALM</td>
        <td>405B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>uiuc-convai/CoALM-405B</td>
    </tr>
    <tr class="single-row">
        <td>Granite</td>
        <td>20B-functioncalling</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>ibm-granite/granite-20b-functioncalling</td>
    </tr>
    <tr class="single-row">
        <td>BitAgent</td>
        <td>8B</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>BitAgent/BitAgent-8B</td>
    </tr>
    <tr class="single-row">
        <td>Haha</td>
        <td>7B</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>ZJared/Haha-7B</td>
    </tr>
    <tr class="single-row">
        <td>Bielik</td>
        <td>11B-v2.3-Instruct</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>speakleash/Bielik-11B-v2.3-Instruct</td>
    </tr>
    <tr class="single-row">
        <td>QwQ</td>
        <td>32B-Preview</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>Qwen/QwQ-32B-Preview</td>
    </tr>
    <tr class="single-row">
        <td>Sky-T1</td>
        <td>32B-Preview</td>
        <td>Prompt</td>
        <td>Self-Hosted</td>
        <td>NovaSky-AI/Sky-T1-32B-Preview</td>
    </tr>
    <tr class="single-row">
        <td>GLM</td>
        <td>4-9B-Chat</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>THUDM/glm-4-9b-chat</td>
    </tr>
    <tr class="single-row">
        <td>ToolACE</td>
        <td>8B</td>
        <td>Function Calling</td>
        <td>Self-Hosted</td>
        <td>Team-ACE/ToolACE-8B</td>
    </tr>
</table>
</div>

<style>
.model-table .expandable-row {
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
}

.model-table .expandable-row:hover {
    background-color: rgb(45, 45, 50);
}

.model-table .hidden {
    display: none;
}
</style>

<script>
function toggleModelRows(clickedRow) {
    // Toggle expanded class for arrow rotation
    clickedRow.classList.toggle('expanded');
    
    let currentRow = clickedRow.nextElementSibling;
    
    // Keep toggling rows until we hit another expandable row or single row or the end
    while (currentRow && !currentRow.classList.contains('expandable-row') && !currentRow.classList.contains('single-row')) {
        currentRow.classList.toggle('hidden');
        currentRow = currentRow.nextElementSibling;
    }
}
</script>

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

