# How to Add New Models

We welcome your contributions to the Leaderboard! This guide provides step-by-step instructions for adding a new model to the leaderboard.

- [How to Add New Models](#how-to-add-new-models)
  - [Repository Structure](#repository-structure)
  - [Where to Begin](#where-to-begin)
  - [Function Calling (FC) Handlers](#function-calling-fc-handlers)
  - [Creating Your Model Handler](#creating-your-model-handler)
  - [Updating Model Config Mapping](#updating-model-config-mapping)
  - [Submitting Your Pull Request](#submitting-your-pull-request)
  - [Join Our Community](#join-our-community)

## Repository Structure

The repository is organized as follows:

```plaintext
berkeley-function-call-leaderboard/
├── bfcl_eval/
|   ├── constants/                # Global constants and configuration values
│   ├── eval_checker/             # Evaluation modules
│   │   ├── ast_eval/             # AST-based evaluation
│   │   ├── multi_turn_eval/      # Multi-turn evaluation
│   ├── model_handler/            # All model-specific handlers
│   │   ├── local_inference/            # Handlers for locally-hosted (open-source) models
│   │   │   ├── base_oss_handler.py       # Single FC handler for all OSS models (vLLM/sglang)
│   │   ├── api_inference/    # Handlers for API-based models
│   │   │   ├── openai.py             # Example: OpenAI models
│   │   │   ├── claude.py             # Example: Claude models
│   │   │   ├── ...
│   │   ├── parser/                # Parsing utilities for Java/JavaScript
│   │   ├── base_handler.py        # Base handler blueprint
│   ├── data/                  # Datasets
│   ├── scripts/               # Helper scripts
├── result/                       # Model responses
├── score/                        # Evaluation results
```

To add a new model, focus primarily on the `model_handler` directory. You do not need to modify the parsing utilities in `model_handler/parser` or any other directories.

## Where to Begin

- **Base Handler:** Start by reviewing `bfcl_eval/model_handler/base_handler.py`. All model handlers inherit from this base class. The `inference_single_turn` and `inference_multi_turn` methods defined there are helpful for understanding the model response generation pipeline. The `base_handler.py` contains many useful details in the docstrings of each abstract method, so be sure to review them.
  - If your model is hosted locally, you should also look at `bfcl_eval/model_handler/local_inference/base_oss_handler.py`.
- **Reference Handlers:** Checkout some of the existing model handlers (such as `openai.py`, `claude.py`, etc); you can likely reuse some of the existing code if your new model outputs in a similar format.
  - If your model is OpenAI-compatible, the `openai.py` handler will be helpful (and you might be able to just use it as is).
  - If your model is locally hosted, review `base_oss_handler.py` — most open-source models run through it directly by setting a vLLM/sglang tool-call parser in the model config.

## Function Calling (FC) Handlers

BFCL evaluates every model through its native function-calling (FC) interface: function definitions are passed in the API's dedicated `tools` section (for API models) or parsed from the served model's native tool-call output via a vLLM/sglang tool-call parser (for locally-hosted models). The chat/prompt-based tool-calling pathway (where function docs were injected into the system prompt and the model's free-text output was parsed back into calls) has been retired.

For API-based models, the handler methods that build requests and parse responses end with `_FC`.

For locally-hosted (open-source) models you usually do **not** need a bespoke handler: point the model config's `model_handler` at `OSSHandler` (in `local_inference/base_oss_handler.py`) and set the appropriate `vllm_tool_call_parser` (and `vllm_reasoning_parser` if the model emits a reasoning trace). Only subclass `OSSHandler` if the model needs custom request/response handling.

## Creating Your Model Handler

**For API-based Models:**

- Implement the methods marked as "not implemented" under the `FC Methods` section in `base_handler.py`.

**For Locally-Hosted Models:**

- In most cases, reuse `OSSHandler` directly: set `model_handler=OSSHandler` and a `vllm_tool_call_parser` in the model config (see above). Only subclass `OSSHandler` if you need to customize request construction or response parsing.

**Common Requirements for All Handlers:**  
Regardless of mode or model type, you should implement the following methods to convert raw model response (output of `_parse_query_response_xxx`) into standard formats expected by the evaluation pipeline:

1. **`decode_ast`**  
   Converts the raw model response into a structured list of dictionaries, with each dictionary representing a function call:

   ```python
   [{"func1": {"param1": "val1", "param2": "val2"}}, {"func2": {"param1": "val1"}}]
   ```

   This helps the evaluation pipeline understand the model’s intended function calls.

2. **`decode_execute`**  
   Converts the raw model response into a list of strings representing callable functions:

   ```python
   ["func1(param1=val1, param2=val2)", "func2(param1=val1)"]
   ```

## Updating Model Config Mapping

1. **Add a new entry in `bfcl_eval/constants/model_config.py`**

   Populate every field in the `ModelConfig` dataclass:

   | Field               | What to put in it                                                                 |
   | ------------------- | --------------------------------------------------------------------------------- |
   | **`model_name`**    | Model name as used in the API or on Hugging Face.                                 |
   | **`display_name`**  | Model name as it should appear on the leaderboard.                                |
   | **`url`**           | Link to the model’s documentation, homepage, or repo.                             |
   | **`org`**           | Company or organization that developed the model.                                 |
   | **`license`**       | License under which the model is released. `Proprietary` if it’s not open-source. |
   | **`model_handler`** | Name of the handler class (e.g., `OpenAIHandler`, `GeminiHandler`).               |

2. **(Optional) Add pricing**

   If the model is billed by token usage, specify prices _per million tokens_:

   ```python
   input_price  = 0.50   # USD per 1M input tokens
   output_price = 1.00   # USD per 1M output tokens
   ```

   For free/open-source models, set both to `None`.

3. **Set behavior flags**

   | Flag                    | When to set it to `True`                                                                                                      |
   | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
   | **`is_fc_model`**       | Marks the model as a function-calling model. Set to `True` (the prompt-based pathway has been retired).                       |
   | **`underscore_to_dot`** | Your FC model rejects dots (`.`) in function names; set this so the dots will auto-converts to underscores during evaluation. |

4. **Update Supported Models**

   1. Add your model to the list of supported models in `SUPPORTED_MODELS.md`. Include the model name in the table.
   2. Add a new entry in `bfcl_eval/constants/supported_models.py` as well.

## Submitting Your Pull Request

- Raise a [Pull Request](https://github.com/ShishirPatil/gorilla/pulls) with your new Model Handler and the necessary updates to the model config.
- Ensure that the model you add is publicly accessible, either open-source or behind a publicly available API. While you may require authentication, billing, registration, or tokens, the general public should ultimately be able to access the endpoint.
  - If your model is not publicly accessible, we would still welcome your contribution, but we unfortunately cannot include it in the public-facing leaderboard.

## Join Our Community

- Have questions or need help? Join the [Discord](https://discord.gg/grXXvj9Whz) and visit the `#leaderboard` channel.
- Feel free to reach out if you have any questions, concerns, or would like guidance while adding your new model. We’re happy to assist!

---

Thank you for contributing to the Berkeley Function Calling Leaderboard! We look forward to seeing your model added to the community.
