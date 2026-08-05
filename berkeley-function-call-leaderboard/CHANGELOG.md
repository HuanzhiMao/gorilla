# Changelog

All notable changes to the Berkeley Function Calling Leaderboard will be documented in this file.

- [Aug 1, 2026] Went through every handler against its provider's current documentation and made the multimodal paths real. Each of the three capabilities — an image in a user message, an mp3 in a user message, and an image returned *by a tool call* — is now declared per handler (`can_handle_image_input` / `can_handle_audio_input` / `can_handle_image_tool_response`), and those declarations are load-bearing rather than decorative.
  1. **The flags now gate.** `skip_rules` in `_llm_response_generation.py` runs a modality only when the model supports it (`supports_*` on the registry row) *and* its handler can put it on the wire (`can_handle_*` on the handler class). Declaring the three flags is enforced at import time on every subclass — `BaseHandler.__init_subclass__` checks the class's own `__dict__`, so inheriting them does not count. A third rule was added for categories whose *tools* return images, marked by the new `tools_return_images` field on the category spec (geoguessr: its question is text, and every image arrives from `StreetViewAPI`). `BaseHandler` also refuses a turn carrying a modality the handler denied, rather than rendering the parts it recognizes — a dropped image scores the model on a question it never saw.
  2. **Crashes on the multimodal paths.** The clarification loop called `self._extract_clarification_context`, which exists on no handler (the free function is imported and was unused), and then handed `_add_next_turn_user_message_FC` a raw dict where every handler now expects a `Message` — so both audio modalities died on the first tool-call-free reply. The OpenAI-completions image tool-response path built its follow-up user message as a hand-rolled dict with an `image_content` key and fed it back through `add_first_turn_message_FC`, raising `AttributeError: 'dict' object has no attribute 'has_image'` for all 25 image-capable models on the OpenAI protocol. Mistral, Cohere and Gorilla had no `ResultType.IMAGE` branch at all and dropped an `ImageResult` dict — raw JPEG bytes included — into a string-typed content field. `OpenAIResponsesHandler` appended `tool_message` outside the branch that binds it.
  3. **Content-less messages.** A `true_audio` message has audio and no text, and every handler emitted its text part unconditionally: `{"type": "text", "text": null}` (400 from Anthropic), `{"text": None}` (client-side `ParamValidationError` from botocore), `Part(text=None)` (400 from Gemini), `TextChunk(text=None)` (pydantic failure inside the Mistral SDK). Text parts are now emitted only when there is text.
  4. **Audio support added where the provider has it.** Gemini takes mp3 through the same inline-data part as images (`audio/mp3`). vLLM's OpenAI-compatible server accepts `input_audio`, which is what the five audio-native OSS models need. The Chat Completions renderer no longer discards the accompanying text when a message also carries audio. Conversely, Mistral's `input_audio` chunk was removed: only Voxtral accepts it, and this handler serves `mistral-large-2512`. Claude, Nova, the OpenAI Responses API, Cohere, Writer, Grok, GLM, DeepSeek, Kimi, Ling, MiMo and Nanbeige take no audio at all — verified against each provider's own reference, not inferred.
  5. **Image support added where it was missing.** Cohere Chat v2 accepts an `image_url` content part (Command A Vision) and its tool messages do not, so `CohereHandler` renders images and delivers tool-result images through the following-user-message workaround. `KimiHandler`'s override, which put an `image_url` part inside a `role="tool"` message, was deleted in favour of the inherited documented path — no Moonshot page sanctions array content on a tool message, and the OpenAI-compatible schema it implements narrows that field to text. Restore it only against a live probe.
  6. **Multimodal payloads survived merging and logging.** `combine_consecutive_user_prompts` (which runs on every Claude and Nova turn) folded only `content`, silently discarding the merged-away message's images, audio and clarification metadata. Inference logs redacted binary payloads only for vision categories, so an mp3 was stringified into every audio result file. `extract_clarification_context` cleared the metadata it read, and is called once per step — so only the first clarification of a turn could ever be approved; it is now a pure read that also falls back to the audio sidecar's transcript.
  7. **Two deliberate payload changes beyond the multimodal paths.** Claude's prompt cache marker was written to `content[0]` of the last two user messages; a `cache_control` marker ends the cached prefix *at* that block, so on a vision turn it excluded the image — the only part worth caching. It now goes on the last block, which also changes where the breakpoint lands on a **text** multi-turn round that returns several tool results at once (cache economics only; the prompt itself is unchanged). And the OpenAI Responses handler emitted image parts before the text part while every other handler emits text first; it now matches them, so the leaderboard compares providers on the same prompt structure.
  8. **Per-model support corrected where the registry contradicted the vendor.** All three Gemini rows list "Text, Image, Video, Audio, and PDF" on their own model pages (image and audio both confirmed against the live API), but two had `supports_image_input=False` and all three had `supports_audio_input=False`. `palmyra-x5` is the model Writer's own "chat with images" guide uses by name, and its SDK gates the image content fragment to exactly that model, but the row said no image support. Everything else in the registry matched.
  9. **Clarification (audio only) stopped burning a judge call it could never win.** `check_for_clarification` now returns early when the entry lists no allowed clarifications: rule 3 of the judge prompt requires every requested topic to appear in that list, so an empty one guarantees a refusal — and reaching the judge at all made an `OPENAI_API_KEY` a hard requirement for scoring a *self-hosted* model on the audio categories. A clarification round now also counts against `MAXIMUM_STEP_LIMIT`, which it previously escaped.
  10. **Logging.** `inference_input_log` `repr()`s the rendered provider payload, which for a multimodal turn is up to a megabyte of base64 per image and ~57KB per audio clip, written once per step. It now goes through a redactor that elides the payloads and keeps the shape. Redacted audio also serializes as text rather than as `b""`, which was reaching the result file as the literal string `b''`.
  11. **Coverage.** `tests/test_handler_multimodal.py` renders an image turn, an audio turn, a text turn, an image tool result and a text tool result through every handler class — including the five that ship without a registry row, which the registry-derived parametrization would otherwise skip — and asserts the payload actually carries the bytes and never carries a null text field. One case drives a real `vision_web_search` entry end to end rather than a synthetic message. The existing per-handler request snapshots are unchanged, so nothing a text category sends has moved apart from item 7.

- [Jul 31, 2026] Replaced the untyped dictionaries used for test entries, ground truth, and generated artifacts with a dataclass-based data model in the new `bfcl_eval/schemas/` package. The refactor itself is behavior-preserving, verified three ways: the AST checker's verdict was compared entry by entry against the previous implementation across all ten AST categories (zero differences over ~2,470 entries); the literal kwargs handed to each vendor SDK were captured on both the old and new code paths and are byte-identical (15 handler classes, 810 payloads); and the new loader's output was compared against the legacy dict loader for every loadable category, entry for entry. **Six defects the refactor exposed are then fixed deliberately — four of them change what the model receives, so scores from before this release are not comparable.** See items 7 and 8.
  1. **New typed vocabulary.** `TestEntry` (plus `AstTestEntry`, `MultiTurnTestEntry`, `AgenticTestEntry`, `MemoryTestEntry`, `VisionTestEntry`, `FailingToolsTestEntry`), `GroundTruth` (a tagged union: `AstGroundTruth`, `MultiTurnGroundTruth`, `TextAnswerGroundTruth`, `CoordinateGroundTruth`, `CallConstraintGroundTruth`, `NoGroundTruth`), `Conversation`/`Message`/`ImageContent`/`AudioContent`, `FunctionDoc`/`ParameterSchema`, `ToolEnvironment`/`MissedClassRule`/`FailureInjection`, and `ModelResultEntry`/`ScoreHeader`/`ScoreRecord`. This closes the standing FIXME asking for a data class around the audio and image message payloads.
  2. **`ExpectedFunctionCall`** replaces the single-key `{func_name: params}` dict whose shape was assumed, unchecked, by three separate `list(possible_answer.values())[0]` unwraps in the AST checker. The invariant is now enforced at parse time and verified across the corpus.
  3. **`TestCategory` + a `CategorySpec` registry** replace ~30 substring-matching predicates. Each category is one declarative row naming its files, eval strategy, ground-truth shape, and traits, so the order-sensitive if/elif chain in `evaluate_task` becomes a dict lookup. Behavior is unchanged and proven by a parity test over every trait × every category; three couplings that previously worked only by coincidence of spelling — vision web search receiving the agentic system prompt, `is_true_audio` matching `text_audio`, and the runner dispatch ordering — are now explicit fields.
  4. **Handler contract change.** `_pre_query_processing_FC`, `_compile_tools`, `add_first_turn_message_FC`, and `_add_next_turn_user_message_FC` now receive a `TestEntry` and `list[Message]` instead of raw dicts, and build provider payloads from those fields rather than mutating the entry in place. Custom handlers must be updated; see the new "Working With Test Entries" section in `CONTRIBUTING.md`.
  5. **Declarative loading pipeline.** The ~15 post-processors that used to run from an if/elif chain inside `load_dataset_entry` now live in `bfcl_eval/dataset_loader/stages/`, and each category declares its own ordered `load_stages` in the registry, so "what happens to my category on the way in?" is one row rather than a trace through the loader. `bfcl_eval.dataset_loader.pipeline.describe(category)` prints it. The legacy dict loader in `bfcl_eval.utils` is deliberately kept as an independent reference implementation, which turns the equivalence test into a real two-implementation comparison. Verified by capturing the literal kwargs handed to each vendor SDK on both code paths -- 15 handler classes, 810 payloads, byte-identical -- plus a content-hash baseline over all 7,787 loaded entries.
  7. **Long-standing defects fixed. Four of these change model-visible input, so previous scores are not comparable for the affected categories.**
     1. *Java and JavaScript were described to the model as Python* (affects `simple_java`, `simple_javascript` and their audio variants). `_get_language_specific_hint` compared its argument against the bare strings `"java"`/`"javascript"` but was only ever called with a category name like `"simple_java"`, so both non-Python branches were unreachable and every tool description ended with "Note that the provided function is in Python 3 syntax." It now takes a `Language`. The AST checker's verdicts are unaffected -- this changes the prompt, not the judging.
     2. *All eight vision web-search variants scored the same, unperturbed image* (affects the seven perturbed `vision_web_search_*` categories). `_VISION_SUFFIX_MAP` was keyed `"vision_bw"`, `"vision_crop_169"`, ... while the lookup key is the base category name `"vision_web_search_bw"`, so the lookup never matched. Re-keyed to the base category names; the perturbation experiment now actually perturbs. A category whose image set is incomplete now **refuses to load**, naming every missing file, rather than substituting the unperturbed image for the entries it cannot perturb -- a category that silently stops measuring its own perturbation while still reporting a score is worse than one that fails. Three variants of image `233` (`_bw`, `_resize_169`, `_resize_43`) are absent from `data/vision/images/`, so `vision_web_search_bw`, `vision_web_search_resize_169` and `vision_web_search_resize_43` are unloadable until those are generated; the other five variants are unaffected.
     3. *`NovaHandler` sent every user message twice.* `add_first_turn_message_FC` appended each rendered message inside its loop and then extended the list with the same messages again.
     4. *Prompt and ground-truth entries could never be paired by id,* so the evaluator paired them by list position -- which silently mis-scores if either file is reordered or partially regenerated. Two causes, both fixed: `load_ground_truth_entry` interpolated the `Modality` enum rather than its value, yielding `"Modality.TEXT:simple_python_0"`; and categories that share a ground-truth file (both `web_search_*` share `web_search.json`, the three memory backends share `memory.json`) had their prompt ids rebranded to name the category but not their ground-truth ids. `_subset_entries_by_model_ids` now pairs by id and raises on a mismatch.
     5. *An unreadable `initial_config` silently dropped the entry,* so a dataset typo quietly reduced the number of scored entries instead of failing the run. It is now an error.
     6. Removed the unreachable `parallel_function_checker_enforce_order`, and fixed `scripts/visualize_multi_turn_ground_truth_conversation.py`, which passed the pre-`modality:` category name `"text_multi_turn"` and so could not even be imported.
  8. **Known dataset gaps, not fixable in code.** `possible_answer/vision/vision_base.json` holds 52 expected answers against 250 vision web-search prompts, so those categories remain unscorable until the missing 198 are authored. The audio modalities still cannot load: their files live in `data/audio/text_audio/` rather than `data/audio/`, two carry a `_transformed` suffix, `multi_turn_miss_func_transformed.json` still uses the retired `missed_function` schema (a dict keyed by turn index) instead of `missed_classes`, and `process_audio_test_case` deletes `asr_output_*` keys that the clean audio files do not have at all. That is a dataset migration rather than a code fix, and no audio model has ever been evaluated.
- [Jul 31, 2026] Added eight models. Seven are self-hosted, with parsers and required serve flags taken from vLLM's own recipes (recipes.vllm.ai) rather than the model cards: `ByteDance-Seed/Seed-OSS-36B-Instruct` (`seed_oss`), `inclusionAI/Ling-2.6-flash` (107B, non-thinking, `hermes` — see the FIXME), `MiniMaxAI/MiniMax-M3` (427B, image+video in, `minimax_m3`, `--block-size 128` is mandatory, thinking pinned to `enabled` instead of `adaptive`), `stepfun-ai/Step-3.7-Flash` (201B VL, `step3p5`, `--disable-cascade-attn` is required for correctness), `tencent/Hy3` (299B, `hy_v3`, run at `reasoning_effort: "high"` since it does not think by default), `thinkingmachines/Inkling-Small` (266B, image+audio in, `inkling`, needs `--tokenizer-mode inkling`), and `XiaomiMiMo/MiMo-V2.5` (311B omnimodal, `mimo`, thinking turned on per request). The eighth, `mimo-v2.5-pro`, is 1.02T and therefore goes through Xiaomi's OpenAI-compatible API (`MIMO_API_KEY`, new `MiMoHandler`). Two more trillion-parameter models come with them: `Ling-2.6-1T` on Ant's Bailing/Tbox API, which brings back `LingAPIHandler` (deleted with the prompting pathway) as an FC-only handler, and `thinkingmachines/Inkling` (952B), self-hosted as a deliberate exception to the ~500B rule because Thinking Machines ships no first-party API and the only alternative was an aggregator. That exception is now written down as rule 4 in `model_config.py`.
- [Jul 30, 2026] Added OpenAI's open-weight `gpt-oss` models as self-hosted entries: `openai/gpt-oss-120b` and `openai/gpt-oss-20b` (both Apache 2.0). They emit OpenAI's harmony format instead of a plain chat template, and vLLM switches to its HarmonyParser off the model config alone, so reasoning content is split out with no `--reasoning-parser` flag; tool calls still need `--tool-call-parser openai --enable-auto-tool-choice`, per the vLLM recipe. Both run at harmony's default `medium` reasoning effort. The `gpt-oss-safeguard-*` variants are deliberately left out — they are safety classifiers, not function-calling models.
- [Jul 30, 2026] Settle how a model's hosting pathway is chosen, and re-sort every entry accordingly. Public weights mean we self-host, so the score reflects the model rather than a provider's serving stack — except above ~500B total parameters, where self-hosting stops being reproducible for most people and we use the vendor API instead. No model appears in both maps any more. The rule is written down at the top of `model_config.py`. Breaking change: model IDs move in both directions with no aliasing, and result/score directories change accordingly.
  1. `mistral-medium-3-5` → `mistralai/Mistral-Medium-3.5-128B`, now that Mistral has released open weights for Medium 3.5 under a Modified MIT license. Served with the `mistral` tool-call and reasoning parsers, in reasoning mode (`reasoning_effort="high"`), which Mistral recommends for agentic use.
  2. `glm-4.6v` → `zai-org/GLM-4.6V` and `glm-4.6v-flash` → `zai-org/GLM-4.6V-Flash` (both MIT), with `glm45` for both tool calls and reasoning. `vision_model_map` is now empty: vision-capable models are not a separate hosting pathway, they are just entries flagged with `supports_image_input=True`.
  3. Replaced all three Cohere entries — `CohereLabs/c4ai-command-a-03-2025`, `CohereLabs/command-a-reasoning-08-2025`, and `CohereLabs/command-a-vision-07-2025` — with the single self-hosted `CohereLabs/command-a-plus-05-2026-bf16`. Command A+ supersedes the trio (one model for agentic tool use, reasoning, and vision), is Apache 2.0 instead of cc-by-nc-4.0, and is ungated. Served with the `cohere_command4` tool-call and reasoning parsers per Cohere's model card; that parser imports `cohere_melody`, which is not a vLLM dependency, so it has been added to the `oss_eval_vllm` extra. The old entries were routed to the Cohere API handler despite being keyed by HuggingFace repo ids, so no Cohere API model remains; `CohereHandler` and the `cohere` SDK dependency are now unused.
  4. Moved the three self-hosted entries above 500B parameters to API inference. `mistralai/Mistral-Large-3-675B-Instruct-2512` (675B) → the new `mistral-large-2512` entry, the pinned id for the 25.12 release. `zai-org/GLM-5.2` (753B) → `glm-5.2` on the Z.ai API. The `deepseek-ai/DeepSeek-V4-Pro` entry (1.6T) is dropped outright: the `DeepSeek-V4-Pro` API entry already covers that model, so the `(self-hosted)` display name introduced on Jul 29 to disambiguate the two is no longer needed. Parameter counts are the `safetensors.total` figures HuggingFace reports, not name-derived guesses.
  5. Dropped `mistral-small-2603`, the API twin of `mistralai/Mistral-Small-4-119B-2603`. At 119B the model is well inside the self-hosting range, and the two entries were the same weights scored twice.
  6. Not converted, with reasons recorded in `model_config.py`: `kimi-k3` has open weights but is 2.8T parameters, and vLLM ships its `kimi_k3` parsers only on `main`, not in any release through v0.26.0. `deepseek-v4-flash`, `grok-4.5`, `palmyra-x5`, `muse-spark-1.1`, `Nanbeige3.5-Pro-Thinking`, `glm-5v-turbo`, and the GPT/Claude/Gemini/Nova entries have no public weights.
- [Jul 29, 2026] Follow-up cleanup now that every model runs in FC mode. This lands as part of the next major BFCL release, which intentionally breaks compatibility with earlier versions; handlers and configs written against the previous release are not supported as-is.
  1. Dropped the redundant `(FC)` suffix from every leaderboard display name. `GLM-5.1 (FC thinking)` becomes `GLM-5.1 (thinking)`, and the self-hosted DeepSeek entry is now `DeepSeek-V3.2 (self-hosted)` so it no longer collides with the API entry.
  2. Removed the `is_fc_model` field from `ModelConfig` and the corresponding constructor argument from `BaseHandler` and every model handler. It was `True` for all models and gated no remaining behavior. Breaking change: custom handlers must drop the argument from their `__init__` signature and `super().__init__(...)` call.
  3. Locally-hosted models now receive every test entry exactly as written, with no message normalization. A few `live_irrelevance` entries contain consecutive user turns, and some chat templates (Gemma's, for one) reject those outright. We deliberately do not merge them: real-world queries are noisy, so a template that cannot accept them is a genuine model limitation and should be reflected in the score rather than hidden by a benchmark-side rewrite. Affected entries are recorded as inference errors and scored as failures; the rest of the run is unaffected. Note that the Claude and Nova handlers still merge consecutive user messages, because their APIs reject them at the API layer rather than in a chat template.
  4. Fixed `mistralai/Mistral-Small-4-119B-2603`, which was routed to the Mistral API handler instead of being served locally, and `qwen3-4b-nothink`, whose handler could not be constructed.
  5. Regenerated `SUPPORTED_MODELS.md` from the model registry and dropped its now-uniform `Type` column.
  6. Dropped the redundant `-FC` suffix from all 43 affected model IDs in the registry, so `--model claude-opus-5-FC` is now `--model claude-opus-5`. With the prompting pathway gone the suffix distinguished nothing, and it was already absent from 20 of the 63 IDs. Breaking change, with no aliasing of the old names: update any scripts that pass a `-FC` model ID, and note that the result/score directory for a renamed model changes accordingly, so results generated before this change will not be picked up by `bfcl evaluate` unless their directories are renamed to match. The `Salesforce/*-fc-r` IDs are unaffected — that suffix is part of the upstream HuggingFace repo name. Also removed the now-dead suffix stripping in the Claude, Cohere, and Qwen handlers, and dropped the stray `-FC` from the two Qwen Agent entries' vendor `model_name` values, where it had been compensated for at call time.
- [Jul 28, 2026] Drop support for a set of models and providers that are no longer actively tracked, to reduce maintenance surface. BFCL now focuses on models from major labs and providers; the community is welcome to add support for other models in a fork.
  1. Removed the `Bielik`, `Arch-Agent` (katanemo), `BitAgent`/`GoGoAgent` (Bittensor), and `Falcon3` (TII UAE) model entries and their handlers.
  2. Removed Novita AI as a third-party inference provider, along with the `NOVITA_AI` model style, the `NovitaHandler`, and the `NOVITA_API_KEY` setting. The Llama-4-Maverick, Llama-4-Scout, and QwQ-32B models previously served via Novita remain available as self-hosted entries.
- [Jul 23, 2026] Retire the prompting (chat-based tool calling) pathway. BFCL now evaluates models exclusively through their native function-calling (FC) interface:
  1. Removed the prompting inference drivers and abstract prompting hooks from the handler base classes, and all `*_prompting` overrides from the model handlers.
  2. Locally-hosted (open-source) models now run through a single FC handler backed by vLLM/sglang tool-call and reasoning parsers; the per-model prompt-mode handlers have been removed.
  3. Retired the non-scoring `format_sensitivity` category (it only applied to prompting-mode models); its dataset manifest has been moved to `bfcl_eval/data/unused_datasets/`. To reproduce past format-sensitivity results, check out a release from before this change.
  4. Removed prompt-mode-only model entries. Models that had a paired FC entry remain on the leaderboard via that entry; models that had no FC entry have been removed and can return once evaluated in FC mode.
- [Oct 1, 2025] [#1177](https://github.com/ShishirPatil/gorilla/pull/1177): Fix ground truth for `multi_turn_base_154`.
- [Sep 27, 2025] [#1185](https://github.com/ShishirPatil/gorilla/pull/1185): Introduce the `--partial-eval` flag to the `bfcl evaluate` command, allowing partial evaluation on a subset of available test entries in the model result files.
- [Sep 17, 2025] [#1175](https://github.com/ShishirPatil/gorilla/pull/1175): Fix wrong date in ground truth for `live_simple_205-116-13`.
- [Jul 17, 2025] [#1019](https://github.com/ShishirPatil/gorilla/pull/1019): BFCL V4 release:

  1. **New agentic domain**
     - Introduces the agentic domain with two categories: Web Search and Memory Management.
     - For more information, please see our accompanying [blog posts](https://gorilla.cs.berkeley.edu/blog.html).
  2. **Revised overall-accuracy formula**

     - As single-turn tasks approach saturation, weighting now favors complex, multi-step agentic tasks.

     | Segment     | Old % |  New % |
     | ----------- | ----: | -----: |
     | Live        |    33 | **10** |
     | Non-Live    |    33 | **10** |
     | Irrelevance |     0 | **10** |
     | Multi-Turn  |    33 | **30** |
     | Agentic     |     0 | **40** |

  3. **Leaderboard / model cleanup**
     - Retires several deprecated models from the leaderboard.
     - Removes unused model handlers to improve maintainability.
  4. **Address #602**
     - `Non-Live Acc` and `Live Acc` score calculation now excludes the Irrelevance/Relevance category scores.
  5. **Resolve #1094.**
  6. **Codebase refactor**
     - Reorganizes the response-generation pipeline and related modules for easier maintenance.
     - Simplify the response-generation pipeline logic for locally-hosted models.
     - Introduce `enums.py`
  7. **Test category rename**
     The following categories have been renamed to avoid confusion. This applies to both dataset file names and leaderboard website columns.
     - `simple` --> `simple_python`
     - `java` --> `simple_java`
     - `javascript` --> `simple_javascript`
  8. **Directory layout overhaul**
     Results and scores now use a _two-level_ hierarchy:

     ```text
     result/<model>/<general_category>/<category>.json
     score/<model>/<general_category>/<category>.json
     ```

     `general_category` ∈ { **non_live**, **live**, **multi_turn**, **agentic**, **format_sensitivity** }

     • For _agentic-memory_ tasks, an extra level distinguishes the memory backend:

     ```text
     result/<model>/agentic/<memory_backend>/<category>.json
     ```

     Migrate existing outputs to this structure before upgrading, otherwise the evaluation pipeline will fail to locate files.
  9. **New model support**
     Adds support for the following models:
     - `claude-opus-4-1-20250805`
     - `gpt-5-2025-08-07`
     - `gpt-5-mini-2025-08-07`
     - `gpt-5-nano-2025-08-07`
     - `Qwen/Qwen3-30B-A3B-Instruct-2507`
     - `Qwen/Qwen3-235B-A22B-Instruct-2507`
     - `Qwen/Qwen3-4B-Instruct-2507`

- [Jul 8, 2025] [#1098](https://github.com/Shishirtil/gorilla/pull/1098):
  - Re-introduce latency statistics for locally hosted models
  - Update cost calculation to cover the entire dataset batch, instead of the average cost per 1k function calls
- [Jul 6, 2025] [#1100](https://github.com/ShishirPatil/gorilla/pull/1100): Add the following new models to the leaderboard:
  - `gemini-2.5-pro-FC`
  - `gemini-2.5-pro`
  - `gemini-2.5-flash-FC`
  - `gemini-2.5-flash`
  - `gemini-2.5-flash-lite-preview-06-17-FC`
  - `gemini-2.5-flash-lite-preview-06-17`
- [Jul 6, 2025] [#1099](https://github.com/ShishirPatil/gorilla/pull/1099): Migrate Gemini inference to Google AI Studio.
- [Jul 2, 2025] [#1090](https://github.com/ShishirPatil/gorilla/pull/1090): Updated OpenAI models to use `developer` role instead of `system` role, following OpenAI's documentation recommendations. This change affects only the OpenAI Responses handler.
- [Jul 2, 2025] [#1062](https://github.com/ShishirPatil/gorilla/pull/1062): Introduce OpenAI Responses handler, and add support for `o3-2025-04-16` and `o4-mini-2025-04-16`.
- [Jun 30, 2025] [#956](https://github.com/ShishirPatil/gorilla/pull/956): Fix typo in ground truth for multi_turn_base.
- [Jun 29, 2025] [#1034](https://github.com/ShishirPatil/gorilla/pull/1034): Add support for `claude-opus-4-20250514` and `claude-sonnet-4-20250514`
- [Jun 29, 2025] [#1086](https://github.com/ShishirPatil/gorilla/pull/1086): Fix duplicate test entry ID `live-relevance_3-3-0`.
- [Jun 29, 2025] [#1087](https://github.com/ShishirPatil/gorilla/pull/1087): Add missing base-cost definitions for three airport routes in `travel_booking` backend.
- [Jun 28, 2025] [#1085](https://github.com/ShishirPatil/gorilla/pull/1085): Fix question wording for `irrelevance_232`.
- [Jun 28, 2025] [#1084](https://github.com/ShishirPatil/gorilla/pull/1084): Fix typo in ground truth for `parallel_multiple_141`.
- [Jun 18, 2025] [#1068](https://github.com/ShishirPatil/gorilla/pull/1068): Fix prompt concatenation issue in Qwen chat template. The self-hosted `Qwen3` models are affected.
- [Jun 15, 2025] [#966](https://github.com/ShishirPatil/gorilla/pull/966): Remove the `travel_cost` parameter from multi-turn backend `TravelAPI.book_flight()` and now compute cost internally to eliminate ambiguity.
- [Jun 15, 2025] [#1060](https://github.com/ShishirPatil/gorilla/pull/1060): Fix multi-turn backend `GorillaFileSystem._get_item()` method to correctly handle `"."` in path strings.
- [Jun 14, 2025] [#1032](https://github.com/ShishirPatil/gorilla/pull/1032): Add `Llama-3.1-Nemotron-Ultra-253B-v1` to the leaderboard.
- [Jun 12, 2025] [#1056](https://github.com/ShishirPatil/gorilla/pull/1056): Add `Ling-Lite-V1.5` to the leaderboard.
- [Jun 12, 2025] [#1063](https://github.com/ShishirPatil/gorilla/pull/1063): Add support for `DeepSeek-R1-0528` and `DeepSeek-V3-0324`
- [Jun 11, 2025] [#1061](https://github.com/ShishirPatil/gorilla/pull/1061): Add support for DashScope API inference for `Qwen3` series
- [Jun 8, 2025] [#1054](https://github.com/ShishirPatil/gorilla/pull/1054), [#1055](https://github.com/ShishirPatil/gorilla/pull/1055): Packagerize codebase for PyPI Distribution. Now available with `pip install bfcl-eval`, in addition to the existing `pip install -e`.
- [May 27, 2025] [#1040](https://github.com/ShishirPatil/gorilla/pull/1040): Add the following new models to the leaderboard:
  - `mistral-medium-2505`
  - `mistral-medium-2505-FC`
- [May 24, 2025] [#1033](https://github.com/ShishirPatil/gorilla/pull/1033): Remove latency statistics for open-source models
- [May 24, 2025] [#1015](https://github.com/ShishirPatil/gorilla/pull/1015): Add the following new models to the leaderboard:
  - `Qwen/Qwen3-0.6B`
  - `Qwen/Qwen3-0.6B-FC`
  - `Qwen/Qwen3-1.7B`
  - `Qwen/Qwen3-1.7B-FC`
  - `Qwen/Qwen3-4B`
  - `Qwen/Qwen3-4B-FC`
  - `Qwen/Qwen3-8B`
  - `Qwen/Qwen3-8B-FC`
  - `Qwen/Qwen3-14B`
  - `Qwen/Qwen3-14B-FC`
  - `Qwen/Qwen3-32B`
  - `Qwen/Qwen3-32B-FC`
  - `Qwen/Qwen3-30B-A3B`
  - `Qwen/Qwen3-30B-A3B-FC`
  - `Qwen/Qwen3-235B-A22B`
  - `Qwen/Qwen3-235B-A22B-FC`
- [May 20, 2025] [#1014](https://github.com/ShishirPatil/gorilla/pull/1014): Add support for API inference for `QwQ-32B`
- [Apr 24, 2025] [#1002](https://github.com/ShishirPatil/gorilla/pull/1002): Add the following new models to the leaderboard:
  - `gpt-4.1-2025-04-14-FC`
  - `gpt-4.1-2025-04-14`
  - `gpt-4.1-mini-2025-04-14-FC`
  - `gpt-4.1-mini-2025-04-14`
  - `gpt-4.1-nano-2025-04-14-FC`
  - `gpt-4.1-nano-2025-04-14`
- [Apr 23, 2025] [#1000](https://github.com/ShishirPatil/gorilla/pull/1000): Add new model `microsoft/phi-4` to the leaderboard.
- [Apr 23, 2025] [#967](https://github.com/ShishirPatil/gorilla/pull/967): Add the following new models to the leaderboard:
  - `microsoft/Phi-4-mini-instruct`
  - `microsoft/Phi-4-mini-instruct-FC`
- [Apr 22, 2025] [#997](https://github.com/ShishirPatil/gorilla/pull/997): Several outdated or deprecated models will be excluded from the leaderboard and replaced with their updated successors to improve the leaderboard's overall maintainability.
- [Apr 14, 2025] [#987](https://github.com/ShishirPatil/gorilla/pull/987): Add the following new models to the leaderboard:
  - `grok-3-beta`
  - `grok-3-beta-FC`
  - `grok-3-mini-beta`
  - `grok-3-mini-beta-FC`
- [Apr 14, 2025] [#985](https://github.com/ShishirPatil/gorilla/pull/985): Support fully offline inference via the `--local-model-path` flag. Point it to a directory that already holds the model's files (`config.json`, tokenizer, weights, etc.); use this flag only when the model has been pre‑downloaded outside the default $HF_HOME cache.
- [Apr 13, 2025] [#980](https://github.com/ShishirPatil/gorilla/pull/980): Integrate Novita AI as a third-party inference provider for the following open-source models:
  - `Llama-4-Maverick-17B-128E-Instruct-FP8` (Prompt & FC)
  - `Llama-4-Scout-17B-16E-Instruct` (Prompt & FC)
  - `Qwen/QwQ-32B` (Prompt & FC),
- [Apr 13, 2025] [#981](https://github.com/ShishirPatil/gorilla/pull/981): Add the following new models to the leaderboard:
  - `meta-llama/Llama-4-Scout-17B-16E-Instruct-FC`
  - `meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8-FC`
- [Apr 9, 2025] [#943](https://github.com/ShishirPatil/gorilla/pull/943): Retire the executable categories from the leaderboard. The following categories will be excluded from the evaluation pipeline:
  - `rest`
  - `exec_simple`
  - `exec_parallel`
  - `exec_multiple`
  - `exec_parallel_multiple`
- [Apr 9, 2025] [#972](https://github.com/ShishirPatil/gorilla/pull/972): Add the following new models to the leaderboard:
  - `Salesforce/Llama-xLAM-2-70b-fc-r`
  - `Salesforce/Llama-xLAM-2-8b-fc-r`
  - `Salesforce/xLAM-2-32b-fc-r`
  - `Salesforce/xLAM-2-3b-fc-r`
  - `Salesforce/xLAM-2-1b-fc-r`
- [Apr 8, 2025] [#979](https://github.com/ShishirPatil/gorilla/pull/979): Fix typo in `multi_turn_base_166` ground truth.
- [Apr 6, 2025] [#974](https://github.com/ShishirPatil/gorilla/pull/974): Add the following new models to the leaderboard:
  - `gemini-2.5-pro-exp-03-25-FC`
  - `gemini-2.5-pro-exp-03-25`
- [Mar 26, 2025] [#963](https://github.com/ShishirPatil/gorilla/pull/963): Fix wrong date in `live_simple_205-116-13`.
- [Mar 25, 2025] [#962](https://github.com/ShishirPatil/gorilla/pull/962): Fix ambiguous user query in `exec_parallel_10`.
- [Mar 20, 2025] [#951](https://github.com/ShishirPatil/gorilla/pull/951): Add new model `command-a-03-2025-FC` to the leaderboard.
- [Mar 15, 2025] [#942](https://github.com/ShishirPatil/gorilla/pull/942): Add the following new models to the leaderboard:
  - `gemini-2.0-flash-lite-001-FC`
  - `gemini-2.0-flash-lite-001`
  - `gemini-2.0-flash-thinking-exp-01-21`
- [Mar 13, 2025] [#939](https://github.com/ShishirPatil/gorilla/pull/939): Add the following new models to the leaderboard:
  - `google/gemma-3-1b-it`
  - `google/gemma-3-4b-it`
  - `google/gemma-3-12b-it`
  - `google/gemma-3-27b-it`
- [Mar 13, 2025] [#941](https://github.com/ShishirPatil/gorilla/pull/941): Add new model `Team-ACE/ToolACE-2-8B` to the leaderboard.
- [Mar 2, 2025] [#923](https://github.com/ShishirPatil/gorilla/pull/923): Add the following new models to the leaderboard:
  - `claude-3-7-sonnet-20250219`
  - `claude-3-7-sonnet-20250219-FC`
- [Feb 28, 2025] [#925](https://github.com/ShishirPatil/gorilla/pull/925): Add support for the `Qwen2.5` models in Function Calling mode:
  - `Qwen/Qwen2.5-0.5B-Instruct-FC`
  - `Qwen/Qwen2.5-1.5B-Instruct-FC`
  - `Qwen/Qwen2.5-3B-Instruct-FC`
  - `Qwen/Qwen2.5-7B-Instruct-FC`
  - `Qwen/Qwen2.5-14B-Instruct-FC`
  - `Qwen/Qwen2.5-32B-Instruct-FC`
  - `Qwen/Qwen2.5-72B-Instruct-FC`
- [Feb 28, 2025] [#926](https://github.com/ShishirPatil/gorilla/pull/926): Add support for local inference for `deepseek-ai/DeepSeek-R1`
- [Feb 27, 2025] [#922](https://github.com/ShishirPatil/gorilla/pull/922): Add the following new models to the leaderboard:
  - `gpt-4.5-preview-2025-02-27`
  - `gpt-4.5-preview-2025-02-27-FC`
- [Feb 26, 2025] [#901](https://github.com/ShishirPatil/gorilla/pull/901): Add new model `DeepSeek-R1` to the leaderboard.
- [Feb 24, 2025] [#917](https://github.com/ShishirPatil/gorilla/pull/917): Add new model `BitAgent/BitAgent-8B` to the leaderboard.
- [Feb 5, 2025] [#900](https://github.com/ShishirPatil/gorilla/pull/900), [#913](https://github.com/ShishirPatil/gorilla/pull/913): Add the following new models to the leaderboard:
  - `uiuc-convai/CoALM-8B`
  - `uiuc-convai/CoALM-70B`
  - `uiuc-convai/CoALM-405B`
- [Feb 5, 2025] [#902](https://github.com/ShishirPatil/gorilla/pull/902): Add the following new models to the leaderboard:
  - `gemini-2.0-flash-lite-preview-02-05-FC`
  - `gemini-2.0-flash-lite-preview-02-05`
  - `gemini-2.0-flash-001-FC`
  - `gemini-2.0-flash-001`
  - `gemini-2.0-pro-exp-02-05-FC`
  - `gemini-2.0-pro-exp-02-05`
- [Feb 2, 2025] [#898](https://github.com/ShishirPatil/gorilla/pull/898): Add the following new models to the leaderboard:
  - `o3-mini-2025-01-31-FC`
  - `o3-mini-2025-01-31`
- [Jan 28, 2025] [#894](https://github.com/ShishirPatil/gorilla/pull/894): Add the following new models to the leaderboard:
  - `tiiuae/Falcon3-1B-Instruct-FC`
  - `tiiuae/Falcon3-3B-Instruct-FC`
  - `tiiuae/Falcon3-7B-Instruct-FC`
  - `tiiuae/Falcon3-10B-Instruct-FC`
- [Jan 27, 2025] [#895](https://github.com/ShishirPatil/gorilla/pull/895): Fix minor typo in default system prompt for prompting models.
- [Jan 20, 2025] [#887](https://github.com/ShishirPatil/gorilla/pull/887): Add new model `speakleash/Bielik-11B-v2.3-Instruct` to the leaderboard.
- [Jan 18, 2025] [#888](https://github.com/ShishirPatil/gorilla/pull/888): Add the following new models to the leaderboard:
  - `NovaSky-AI/Sky-T1-32B-Preview`
  - `Qwen/QwQ-32B-Preview`
- [Jan 12, 2025] [#881](https://github.com/ShishirPatil/gorilla/pull/881): Fix Nova handler for consecutive user prompt issue.
- [Jan 11, 2025] : Add new model `ZJared/Haha-7B` to the leaderboard.
- [Jan 4, 2025] [#865](https://github.com/ShishirPatil/gorilla/pull/865): Fix a copy-paste issue in `live_parallel_multiple_9-8-0` that caused a misalignment between the question and the possible answer.
- [Jan 3, 2025] [#864](https://github.com/ShishirPatil/gorilla/pull/864): Add support for pre-existing completion endpoints, allowing users to skip the local vLLM/SGLang server setup (using the `--skip-server-setup` flag) and point the generation pipeline to an existing OpenAI-compatible endpoint via `VLLM_ENDPOINT` and `VLLM_PORT`.
- [Jan 3, 2025] [#859](https://github.com/ShishirPatil/gorilla/pull/859): Rename directories: `proprietary_model` -> `api_inference`, `oss_model` -> `local_inference` for better clarity.
- [Dec 29, 2024] [#857](https://github.com/ShishirPatil/gorilla/pull/857): Add new model `DeepSeek-V3-FC` to the leaderboard.
- [Dec 29, 2024] [#855](https://github.com/ShishirPatil/gorilla/pull/855): Add new model `mistralai/Ministral-8B-Instruct-2410` to the leaderboard.
- [Dec 22, 2024] [#838](https://github.com/ShishirPatil/gorilla/pull/838): Fix parameter type mismatch error in possible answers.
  - Simple: 2 affected
  - Multiple: 1 affected
  - Parallel: 6 affected
  - Parallel Multiple: 4 affected
  - Live Simple: 4 affected
  - Live Multiple: 26 affected
  - Live Parallel: 2 affected
- [Dec 22, 2024] [#843](https://github.com/ShishirPatil/gorilla/pull/843): Add the following new models to the leaderboard:
  - `gemini-2.0-flash-exp-FC`
  - `gemini-2.0-flash-exp`
  - `gemini-exp-1206-FC`
  - `gemini-exp-1206`
- [Dec 21, 2024] [#849](https://github.com/ShishirPatil/gorilla/pull/849): Use `N/A` in score report for unevaluated categories to distinguish from categories where the model actually scored a 0
- [Dec 21, 2024] [#848](https://github.com/ShishirPatil/gorilla/pull/848): Improves behavior for generation and evaluation pipeline. When executable categories are involved and API keys are not provided in the `.env` file, instead of throwing an error, the affected categories will now be skipped. This enhancement provides a smoother experience for first-time users.
- [Dec 21, 2024] [#847](https://github.com/ShishirPatil/gorilla/pull/847): Add new model `watt-ai/watt-tool-8B` and `watt-ai/watt-tool-70B` to the leaderboard.
- [Dec 20, 2024] [#842](https://github.com/ShishirPatil/gorilla/pull/842): Add the following new models to the leaderboard:
  - `Qwen/Qwen2.5-0.5B-Instruct`
  - `Qwen/Qwen2.5-3B-Instruct`
  - `Qwen/Qwen2.5-14B-Instruct`
  - `Qwen/Qwen2.5-32B-Instruct`
- [Dec 18, 2024] [#840](https://github.com/ShishirPatil/gorilla/pull/840): Add the following new models to the leaderboard:
  - `o1-2024-12-17-FC`
  - `o1-2024-12-17`
- [Dec 16, 2024] [#837](https://github.com/ShishirPatil/gorilla/pull/837): Add the following new models to the leaderboard:
  - `meta-llama/Llama-3.3-70B-Instruct-FC`
  - `meta-llama/Llama-3.3-70B-Instruct`
- [Dec 13, 2024] [#832](https://github.com/ShishirPatil/gorilla/pull/832): Add the following new models to the leaderboard:
  - `MadeAgents/Hammer2.1-7b`
  - `MadeAgents/Hammer2.1-3b`
  - `MadeAgents/Hammer2.1-1.5b`
  - `MadeAgents/Hammer2.1-0.5b`
- [Dec 11, 2024] [#826](https://github.com/ShishirPatil/gorilla/pull/826), [#829](https://github.com/ShishirPatil/gorilla/pull/829): Fix `enum` type mismatch error in function doc for live categories.
  - Live Simple: 7 affected
  - Live Multiple: 176 affected
  - Live Parallel Multiple: 3 affected
  - Live Irrelevance: 70 affected
- [Dec 9, 2024] [#822](https://github.com/ShishirPatil/gorilla/pull/822): Add the following new models to the leaderboard:
  - `gpt-4o-2024-11-20`
  - `gpt-4o-2024-11-20-FC`
- [Dec 4, 2024] [#815](https://github.com/ShishirPatil/gorilla/pull/815): Add the following new models to the leaderboard:
  - `nova-pro-v1.0`
  - `nova-lite-v1.0`
  - `nova-micro-v1.0`
- [Dec 3, 2024] [#810](https://github.com/ShishirPatil/gorilla/pull/810): Add new model `grok-beta` to the leaderboard.
- [Dec 2, 2024] [#809](https://github.com/ShishirPatil/gorilla/pull/809): Resolve issue in Gemini model when no model output.
- [Dec 2, 2024] [#808](https://github.com/ShishirPatil/gorilla/pull/808): Improve latency measurement accuracy.
- [Nov 26, 2024] [#755](https://github.com/ShishirPatil/gorilla/pull/755): Add new model `palmyra-x-004` to the leaderboard.
- [Nov 25, 2024] [#718](https://github.com/ShishirPatil/gorilla/pull/718): Add new model `openbmb/MiniCPM3-4B-FC` to the leaderboard.
- [Nov 25, 2024] [#697](https://github.com/ShishirPatil/gorilla/pull/697): Add the following new models to the leaderboard:
  - `deepseek-ai/DeepSeek-V2.5`
  - `deepseek-ai/DeepSeek-Coder-V2-Instruct-0724`
  - `deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct`
  - `deepseek-ai/DeepSeek-V2-Chat-0628`
  - `deepseek-ai/DeepSeek-V2-Lite-Chat`
- [Nov 25, 2024] [#787](https://github.com/ShishirPatil/gorilla/pull/787): Add new model `Qwen/Qwen2.5-72B-Instruct` to the leaderboard.
- [Nov 24, 2024] [#743](https://github.com/ShishirPatil/gorilla/pull/743): Add support for regeneration, specific test entry IDs, and custom directory locations:
  - Introduce the `--allow-overwrite` flag for the `generate` command to enable regeneration of test entries even if they already exist.
  - Add a new `--run-ids` flag for the `generate` command, allowing execution of specific test entry IDs from `test_case_ids_to_generate.json`.
    - Note: This cannot be used together with `--test-category`.
    - Test ids needs to be the exact same as the ones in the dataset. Example: `"simple": ["simple_10", "simple_53"]`.
  - Add `--score-dir` and `--result-dir` options for `generate` and `evaluate` commands, enabling custom paths for result and score directories relative to the project root `berkeley-function-call-leaderboard` directory.
- [Nov 22, 2024] [#777](https://github.com/ShishirPatil/gorilla/pull/777), [#778](https://github.com/ShishirPatil/gorilla/pull/778), [#881](https://github.com/ShishirPatil/gorilla/pull/811): Fix dataset entries where the function doc contains illegal Python parameter names (such as `class`). 55 entries are affected.
- [Nov 19, 2024] [#750](https://github.com/ShishirPatil/gorilla/pull/750): Add the following new models to the leaderboard:
  - `claude-3-5-haiku-20241022`
  - `claude-3-5-haiku-20241022-FC`
  - `claude-3-5-sonnet-20241022`
  - `claude-3-5-sonnet-20241022-FC`
- [Nov 18, 2024] [#736](https://github.com/ShishirPatil/gorilla/pull/736): Add the option to additionally log the evaluation results to [WandB](https://github.com/wandb/wandb) artifacts. User can enable this feature by providing the entity and project name in `WANDB_BFCL_PROJECT` in the `.env` file.
- [Nov 18, 2024] [#768](https://github.com/ShishirPatil/gorilla/pull/768), [#770](https://github.com/ShishirPatil/gorilla/pull/770): Resolve issues in Gemini models (FC mode) related to handling scenarios with no tools available and cases where the model output is empty.
- [Nov 17, 2024] [#767](https://github.com/ShishirPatil/gorilla/pull/767): Fix price and latency calculation. A merge conflict results in a duplicate line, and counting the input and output token for each entry multiple times.
- [Nov 15, 2024] [#762](https://github.com/ShishirPatil/gorilla/pull/762): Supply `data_multi_turn.csv` for multi-turn evaluation results
- [Nov 14, 2024] [#760](https://github.com/ShishirPatil/gorilla/pull/760), [#761](https://github.com/ShishirPatil/gorilla/pull/761): Upstream `google-cloud-aiplatform` library fixed typecasting bugs in Function Calling. Updated to version `1.72.0` and remove the workaround patch introduced in [#648](https://github.com/ShishirPatil/gorilla/pull/648).
- [Nov 14, 2024] [#747](https://github.com/ShishirPatil/gorilla/pull/747): Minor Grammatical Corrections to `DEFAULT_SYSTEM_PROMPT` that is supplied to all prompting models.
- [Nov 13, 2024] [#737](https://github.com/ShishirPatil/gorilla/pull/737), [#739](https://github.com/ShishirPatil/gorilla/pull/739), [#740](https://github.com/ShishirPatil/gorilla/pull/740), [#763](https://github.com/ShishirPatil/gorilla/pull/763), [#772](https://github.com/ShishirPatil/gorilla/pull/772), [#789](https://github.com/ShishirPatil/gorilla/pull/789), [#804](https://github.com/ShishirPatil/gorilla/pull/804): Bug fix in the dataset and possible answers for the live and multi-turn categories.
- [Nov 11, 2024] [#746](https://github.com/ShishirPatil/gorilla/pull/746): Improve inference log readability; inference log is now included as part of the model result file. For details on how to interpret the inference log, please refer to the [LOG_GUIDE.md](https://github.com/ShishirPatil/gorilla/blob/main/berkeley-function-call-leaderboard/LOG_GUIDE.md).
- [Nov 9, 2024] [#749](https://github.com/ShishirPatil/gorilla/pull/749): Remove `Llama-3.2-3B-Instruct-FC` and `Llama-3.2-1B-Instruct-FC` from the leaderboard. According to the [official Llama documentation](<https://www.llama.com/docs/model-cards-and-prompt-formats/llama3_2#-tool-calling-(1b/3b)->), these models perform function calling using the prompt-style chat template rather than the specialized function-calling format.
- [Nov 8, 2024] [#720](https://github.com/ShishirPatil/gorilla/pull/720): Add new model `BitAgent/GoGoAgent` to the leaderboard.
- [Oct 30, 2024] [#725](https://github.com/ShishirPatil/gorilla/pull/725), [#733](https://github.com/ShishirPatil/gorilla/pull/733): Update evaluation metric for multi-turn categories:
  - Introduce a new response-based checker, which works alongside with the existing state-based checker.
    - The new checker compares the model's execution result against the ground truth execution result, ensuring that the model's result encompasses the ground truth (i.e., ground truth must be a strict subset of the model result).
    - It complements the state-based checker, which doesn't work well when the functions don't directly alter the state. For example, it's unclear whether the model actually invoked `get_zipcode_by_city` or `estimate_distance` by just using the state-based checker.
    - Any multi turn entry will now only be marked correct if it passes both the state and response checkers.
  - Remove the irrelevance detection for multi-turn categories.
    - Instead of checking if the model produces no output in a turn with missing function/parameter information, we now assess whether the model can perform correctly once the missing information is provided.
  - A few dataset entries have been modified to align with these changes.
- [Oct 30, 2024] [#719](https://github.com/ShishirPatil/gorilla/pull/719), [#722](https://github.com/ShishirPatil/gorilla/pull/722), [#723](https://github.com/ShishirPatil/gorilla/pull/723), [#728](https://github.com/ShishirPatil/gorilla/pull/728), [#732](https://github.com/ShishirPatil/gorilla/pull/732): Bug fix in the dataset and ground truth for the multi-turn categories.
- [Oct 17, 2024] [#683](https://github.com/ShishirPatil/gorilla/pull/683): Bug fix for the multi turn categories for ambiguity in action intention and function parameters.
- [Oct 17, 2024] [#709](https://github.com/ShishirPatil/gorilla/pull/709): Rephrase question prompt for Java and JavaScript categories to improve clarity and action intent.
- [Oct 17, 2024] [#708](https://github.com/ShishirPatil/gorilla/pull/708): Update the ground truth for the REST category to be up-to-date with the latest API response structure.
- [Oct 16, 2024] [#701](https://github.com/ShishirPatil/gorilla/pull/701): Bug fix the multi turn function source code for `TravelAPI`.
- [Oct 16, 2024] [#696](https://github.com/ShishirPatil/gorilla/pull/696): Add the following new models to the leaderboard:
  - `google/gemma-2-2b-it`
  - `google/gemma-2-9b-it`
  - `google/gemma-2-27b-it`
- [Oct 16, 2024] [#661](https://github.com/ShishirPatil/gorilla/pull/661): Bug fix in the dataset and possible answers.
  - Irrelevance: 1 affected
  - Parallel Multiple: 2 affected
  - Live Simple: 104 affected
  - Live Multiple: 547 affected
  - Live Parallel: 11 affected
  - Live Parallel Multiple: 17 affected
- [Oct 11, 2024] [#667](https://github.com/ShishirPatil/gorilla/pull/667): Add the following new models to the leaderboard:
  - `MadeAgents/Hammer2.0-7b`
  - `MadeAgents/Hammer2.0-3b`
  - `MadeAgents/Hammer2.0-1.5b`
  - `MadeAgents/Hammer2.0-0.5b`
- [Oct 10, 2024] [#621](https://github.com/ShishirPatil/gorilla/pull/621), [#675](https://github.com/ShishirPatil/gorilla/pull/675): Add a basic command-line interface for ease of use.
- [Oct 5, 2024] [#633](https://github.com/ShishirPatil/gorilla/pull/633): Add new model `openbmb/MiniCPM3-4B` to the leaderboard.
- [Oct 5, 2024] [#642](https://github.com/ShishirPatil/gorilla/pull/642): Add the following new models to the leaderboard:
  - `Qwen/Qwen2.5-7B-Instruct`
  - `Qwen/Qwen2.5-1.5B-Instruct`
  - `Qwen/Qwen2-7B-Instruct`
  - `Qwen/Qwen2-1.5B-Instruct`
- [Oct 4, 2024] [#653](https://github.com/ShishirPatil/gorilla/pull/653): Add new model `Team-ACE/ToolACE-8B` to the leaderboard.
- [Oct 4, 2024] [#671](https://github.com/ShishirPatil/gorilla/pull/671): Speed up locally-hosted model's inference process by parallelizing the inference requests.
- [Sept 27, 2024] [#640](https://github.com/ShishirPatil/gorilla/pull/640): Add the following new models to the leaderboard:
  - `microsoft/Phi-3.5-mini-instruct`
  - `microsoft/Phi-3-medium-128k-instruct`
  - `microsoft/Phi-3-medium-4k-instruct`
  - `microsoft/Phi-3-small-128k-instruct`
  - `microsoft/Phi-3-small-8k-instruct`
  - `microsoft/Phi-3-mini-128k-instruct`
  - `microsoft/Phi-3-mini-4k-instruct`
- [Sept 25, 2024] [#660](https://github.com/ShishirPatil/gorilla/pull/660): Bug fix in `parse_nested_value` function to handle nested dictionary values properly.
- [Sept 24, 2024] [#657](https://github.com/ShishirPatil/gorilla/pull/657): Add the following new models to the leaderboard:
  - `meta-llama/Llama-3.2-1B-Instruct`
  - `meta-llama/Llama-3.2-1B-Instruct-FC`
  - `meta-llama/Llama-3.2-3B-Instruct`
  - `meta-llama/Llama-3.2-3B-Instruct-FC`
  - `meta-llama/Llama-3.1-8B-Instruct`
  - `meta-llama/Llama-3.1-8B-Instruct-FC`
  - `meta-llama/Llama-3.1-70B-Instruct`
  - `meta-llama/Llama-3.1-70B-Instruct-FC`
- [Sept 24, 2024] [#648](https://github.com/ShishirPatil/gorilla/pull/648): Add the following new models to the leaderboard:
  - `gemini-1.5-pro-002`
  - `gemini-1.5-pro-002-FC`
  - `gemini-1.5-pro-001`
  - `gemini-1.5-pro-001-FC`
  - `gemini-1.5-flash-002`
  - `gemini-1.5-flash-002-FC`
  - `gemini-1.5-flash-001`
  - `gemini-1.5-flash-001-FC`
  - `gemini-1.0-pro-002`
  - `gemini-1.0-pro-002-FC`
- [Sept 19, 2024] [#644](https://github.com/ShishirPatil/gorilla/pull/644): BFCL V3 release:
  - Introduce new multi-turn dataset and state-based evaluation metric
  - Separate ast_checker and executable_checker for readability
  - Several outdated or deprecated models will be excluded from the leaderboard and replaced with their updated successors to improve the leaderboard's overall maintainability.
  - Switch to use vllm serve for OSS model inference
- [Sept 13, 2024] [#638](https://github.com/ShishirPatil/gorilla/pull/638): Fix prompt formatting issue for `THUDM/glm-4-9b-chat`.
- [Sept 12, 2024] [#635](https://github.com/ShishirPatil/gorilla/pull/635): Add new models `o1-preview-2024-09-12` and `o1-mini-2024-09-12` to the leaderboard.
- [Sept 8, 2024] [#627](https://github.com/ShishirPatil/gorilla/pull/627) Add new model `MadeAgents/Hammer-7b` to the leaderboard.
- [Sept 7, 2024] [#626](https://github.com/ShishirPatil/gorilla/pull/626): Fix prompt format for Llama models.
- [Sept 4, 2024] [#623](https://github.com/ShishirPatil/gorilla/pull/623): Fix decoding issue in the `NvidiaHandler`; remove duplicate `ArcticHandler` class.
- [August 29, 2024] [#616](https://github.com/ShishirPatil/gorilla/pull/6160): Add the following new models to the leaderboard:
  - `Salesforce/xLAM-7b-r`
  - `Salesforce/xLAM-8x7b-r`
  - `Salesforce/xLAM-8x22b-r`
- [August 28, 2024] [#565](https://github.com/ShishirPatil/gorilla/pull/565), [#612](https://github.com/ShishirPatil/gorilla/pull/612): Packagerize the BFCL pipeline for easier deployment and maintenance.
- [August 27, 2024] [#608](https://github.com/ShishirPatil/gorilla/pull/608): Bug fix in the dataset and possible answers.
  - simple: 16 affected
  - multiple: 5 affected
- [August 23, 2024] [#600](https://github.com/ShishirPatil/gorilla/pull/600): Bug fix in the dataset and possible answers.
  - simple: 12 affected
  - multiple: 3 affected
  - parallel: 3 affected
  - parallel multiple: 6 affected
- [August 22, 2024] [#593](https://github.com/ShishirPatil/gorilla/pull/593):
  - Move formatting instructions and function documentation to system prompt instead of user prompt in the message section. All prompting models are affected.
  - Bug fix in the dataset and possible answers.
    - irrelevance: 1 affected
    - live_irrelevance: 1 affected
    - live_simple: 1 affected
    - live_parallel: 3 affected
- [August 19, 2024] [#580](https://github.com/ShishirPatil/gorilla/pull/580): Introduce BFCL V2 Live dataset, featuring user-contributed live prompts and function docs. To read more about the composition and construction of this dataset, please refer to our [blog](https://gorilla.cs.berkeley.edu/blogs/12_bfcl_v2_live.html). All CLI commands have been updated to support the new dataset.
- [August 8, 2024] [#574](https://github.com/ShishirPatil/gorilla/pull/574): Set temperature to 0.001 for all models for consistency and reproducibility.
- [August 7, 2024] [#571](https://github.com/ShishirPatil/gorilla/pull/571): Support parallel inference for hosted models. User can specify the number of threads to use for parallel inference by setting the `--num-threads` flag. The default is 1, which means no parallel inference.
- [August 6, 2024] [#569](https://github.com/ShishirPatil/gorilla/pull/569), [#570](https://github.com/ShishirPatil/gorilla/pull/570), [#573](https://github.com/ShishirPatil/gorilla/pull/573): Add the following new models to the leaderboard:
  - `open-mistral-nemo-2407`
  - `open-mistral-nemo-2407-FC`
  - `open-mixtral-8x22b`
  - `open-mixtral-8x22b-FC`
  - `open-mixtral-8x7b`
  - `gpt-4o-mini-2024-07-18`
  - `gpt-4o-mini-2024-07-18-FC`
  - `gpt-4o-2024-08-06`
  - `gpt-4o-2024-08-06-FC`
  - `meetkai/functionary-medium-v3.1-FC`
  - `meetkai/functionary-small-v3.1-FC`
  - `meetkai/functionary-small-v3.2-FC`
- [August 5, 2024] [#568](https://github.com/ShishirPatil/gorilla/pull/568): Rephrase the question prompt for the `executable_parallel_function` category to remove potentially misleading information implying multi-turn function calls.
- [August 4, 2024] [#557](https://github.com/ShishirPatil/gorilla/pull/557): Bug fix in the possible answers.
  - simple: 7 affected
  - multiple function: 3 affected
  - parallel function: 5 affected
  - parallel multiple function: 6 affected
  - executable parallel function: 1 affected
  - javascript: 3 affected
- [July 26, 2024] [#549](https://github.com/ShishirPatil/gorilla/pull/549): Fix `js_type_converter.py` to properly handle JavaScript array value inside dictionary.
- [July 25, 2024] [#532](https://github.com/ShishirPatil/gorilla/pull/532), [#543](https://github.com/ShishirPatil/gorilla/pull/543), [#556](https://github.com/ShishirPatil/gorilla/pull/556), [#542](https://github.com/ShishirPatil/gorilla/pull/542): Add the following new models to the leaderboard:
  - `Salesforce/xLAM-7b-fc-r`
  - `Salesforce/xLAM-1b-fc-r`
  - `yi-large-fc`
  - `NousResearch/Hermes-2-Pro-Llama-3-8B`
  - `NousResearch/Hermes-2-Pro-Llama-3-70B`
  - `NousResearch/Hermes-2-Theta-Llama-3-8B`
  - `NousResearch/Hermes-2-Theta-Llama-3-70B`
- [July 22, 2024] [#540](https://github.com/ShishirPatil/gorilla/pull/540): Chore: Improve handling of vLLM's cleanup phase error by combining all selected test categories into one single task to submit to the vLLM server.
- [July 21, 2024] [#538](https://github.com/ShishirPatil/gorilla/pull/538), [#545](https://github.com/ShishirPatil/gorilla/pull/545): Fix `language_specific_pre_processing` and `convert_to_tool` function to properly handle pre-processing for prompts and function docs in Java and JavaScript test categories. All entries in these categories are affected.
- [July 20, 2024] [#537](https://github.com/ShishirPatil/gorilla/pull/537): Update generation script for locally-hosted OSS model to use single-node multi-GPU inference method (tensor parallel). Ray is not used anymore.
- [July 16, 2024] [#525](https://github.com/ShishirPatil/gorilla/pull/525), [#536](https://github.com/ShishirPatil/gorilla/pull/536): Add new model `ibm-granite/granite-20b-functioncalling` to the leaderboard.
- [July 10, 2024] [#522](https://github.com/ShishirPatil/gorilla/pull/522): Bug fix in the evaluation dataset for Executable Parallel Multiple category. This includes updates to both prompts and function docs. 2 entries are affected.
- [July 8, 2024] [#516](https://github.com/ShishirPatil/gorilla/pull/516): Fix double-casting issue in `model_handler` for Java and JavaScript test categories.
- [July 7, 2024] [#504](https://github.com/ShishirPatil/gorilla/pull/504), [#505](https://github.com/ShishirPatil/gorilla/pull/505), [#506](https://github.com/ShishirPatil/gorilla/pull/506), [#508](https://github.com/ShishirPatil/gorilla/pull/508), [#512](https://github.com/ShishirPatil/gorilla/pull/512), [#517](https://github.com/ShishirPatil/gorilla/pull/517): Make BFCL user-friendly and easy to extend.
- [July 6, 2024] [#423](https://github.com/ShishirPatil/gorilla/pull/423) and [#503](https://github.com/ShishirPatil/gorilla/pull/503): Bug fix in possible answers for the AST evaluation dataset (parallel category: 14 affected; parallel_multiple category: 25 affected).
- [July 5, 2024] [#496](https://github.com/ShishirPatil/gorilla/pull/496): Updates to API status checks. Checking the health of executable APIs is now off by default. Further, even when triggered, un-healthy APIs will not terminate the evaluation process. Users can enable this feature by setting the `--api-sanity-check` flag or `-c` for short. The previous `--skip-api-sanity-check` or `-s` flag is now deprecated.
- [July 3, 2024] [#489](https://github.com/ShishirPatil/gorilla/pull/489): Add new model `nvidia/nemotron-4-340b-instruct` to the leaderboard.
- [July 2, 2024] [#474](https://github.com/ShishirPatil/gorilla/pull/474): Add new model `THUDM/glm-4-9b-chat` to the leaderboard.
- [June 18, 2024] [#470](https://github.com/ShishirPatil/gorilla/pull/470): Add new model `firefunction-v2-FC` to the leaderboard.
- [June 15, 2024] [#437](https://github.com/ShishirPatil/gorilla/pull/437): Fix prompting issues for `Nexusflow-Raven-v2 (FC)`.
- [June 7, 2024] [#407](https://github.com/ShishirPatil/gorilla/pull/407), [#462](https://github.com/ShishirPatil/gorilla/pull/462): Update the AST evaluation logic to allow the use of `int` values for Python parameters expecting `float` values. This is to accommodate the Python auto-conversion feature from `int` to `float`.
- [May 14, 2024] [#426](https://github.com/ShishirPatil/gorilla/pull/426):
  - Add the following new models to the leaderboard:
    - `gpt-4o-2024-05-13`
    - `gpt-4o-2024-05-13-FC`
    - `gemini-1.5-pro-preview-0514`
    - `gemini-1.5-flash-preview-0514`
  - Update price for the following models:
    - All Gemini Series
    - `Claude-2.1 (Prompt)` and `Claude-instant-1.2 (Prompt)`
    - `Mistral-large` and `Mistral-Small`
    - `GPT-3.5-Turbo-0125`
- [May 8, 2024] [#406](https://github.com/ShishirPatil/gorilla/pull/406) and [#421](https://github.com/ShishirPatil/gorilla/pull/421): Update the `gemini_handler.py` to better handle parallel function calls for Gemini models.
- [May 6, 2024] [#412](https://github.com/ShishirPatil/gorilla/pull/412): Bug fix in evaluation dataset for AST categories. This includes updates to both prompts and function docs.
- [May 2, 2024] [#405](https://github.com/ShishirPatil/gorilla/pull/405): Bug fix in the possible answers for the AST Simple evaluation dataset. Prompt and function docs are not affected.
- [April 28, 2024] [#397](https://github.com/ShishirPatil/gorilla/pull/397): Add new model `snowflake/arctic` to the leaderboard. Note that there are multiple ways to inference the model, and we choose to do it via Nvidia API catalog.
- [April 27, 2024] [#390](https://github.com/ShishirPatil/gorilla/pull/390): Bug fix in cost and latency calculation for open-source models, which are now all calculated when serving the model with [vLLM](https://github.com/vllm-project/vllm) using 8 V100 GPUs for consistency. $$\text{Cost} = \text{Latency per 1000 function call} * (\text{8xV100 azure-pay-as-you-go-price per hour / 3600})$$
- [April 25, 2024] [#386](https://github.com/ShishirPatil/gorilla/pull/386): Add 5 new models to the leaderboard: `meta-llama/Meta-Llama-3-8B-Instruct`, `meta-llama/Meta-Llama-3-70B-Instruct`, `gemini-1.5-pro-preview-0409`, `command-r-plus`, `command-r-plus-FC`.
- [April 19, 2024] [#377](https://github.com/ShishirPatil/gorilla/pull/377):
  - Bug fix for the evaluation dataset in the executable test categories. This includes updates to both prompts and function docs.
  - The `evaluation_result` field has been removed to accommodate the variability in API execution results across different evaluation runs. Instead, a human-verified `ground_truth` is now included for the executable test categories. During each evaluation run, `evaluation_result` is generated anew using the `ground_truth`, and then compared against the model output.
  - A stricter metric has been adopted when using the `structural_match` (aka. type match) evaluation criteria ---- For `list` results, the lengths are compared; for `dict` results, the keys are matched. This is to account for the fast-changing nature of some of the real-time API results while ensuring the evaluation remains meaningful.
  - Added another evaluation criteria `real_time_match` for the executable category, which is a looser form of `exact_match` specifically for numerical execution results. The execution result must be within a certain percentage threshold (20%) from the expected result to accommodate the live updates of API responses. User can change this threshold value in `eval_checker_constant.py`.
- [April 18, 2024] [#375](https://github.com/ShishirPatil/gorilla/pull/375): A more comprehensive API sanity check is included; the APIs that are invoked during the non-REST executable evaluation process will also be checked for their availability before running the evaluation. Also, add support for the shortcut `-s` for the `--skip-api-sanity-check` flag, based on the community feedback.
- [April 16, 2024] [#366](https://github.com/ShishirPatil/gorilla/pull/366): Switch to use Anthropic's new Tool Use Beta `tools-2024-04-04` when generating Claude 3 FC series data. `gpt-4-turbo-2024-04-09` and `gpt-4-turbo-2024-04-09-FC` are also added to the leaderboard.
- [April 11, 2024] [#347](https://github.com/ShishirPatil/gorilla/pull/347): Add the 95th percentile latency to the leaderboard statistics. This metric is useful for understanding the latency distribution of the models, especially the worst-case scenario.
- [April 10, 2024] [#339](https://github.com/ShishirPatil/gorilla/pull/339): Introduce REST API sanity check for the REST executable test category. It ensures that all the API endpoints involved during the execution evaluation process are working properly. If any of them are not behaving as expected, the evaluation process will be stopped by default as the result will be inaccurate. Users can choose to bypass this check by setting the `--skip-api-sanity-check` flag or `-s` for short.
- [April 9, 2024] [#338](https://github.com/ShishirPatil/gorilla/pull/338): Bug fix in the evaluation datasets (including both prompts and function docs). Bug fix for possible answers as well.
- [April 8, 2024] [#330](https://github.com/ShishirPatil/gorilla/pull/330): Fixed an oversight that was introduced in [#299](https://github.com/ShishirPatil/gorilla/pull/299). For function-calling (FC) models that cannot take `float` type in input, when the parameter type is a `float`, the evaluation procedure will convert that type to `number` in the model input and mention in the parameter description that `This is a float type value.`. An additional field `format: float` will also be included in the model input to make it clear about the type. Updated the model handler for Claude, Mistral, and OSS to better parse the model output.
- [April 8, 2024] [#327](https://github.com/ShishirPatil/gorilla/pull/327): Add new model `NousResearch/Hermes-2-Pro-Mistral-7B` to the leaderboard.
- [April 3, 2024] [#309](https://github.com/ShishirPatil/gorilla/pull/309): Bug fix for evaluation dataset possible answers. Implement **string standardization** for the AST evaluation pipeline, i.e. removing white spaces and a subset of punctuations (`,./-_*^`) to make the AST evaluation more robust and accurate. Fixed AST evaluation issue for type `tuple`. Add 2 new models `meetkai/functionary-small-v2.4 (FC)`, `meetkai/functionary-medium-v2.4 (FC)` to the leaderboard.
- [April 1, 2024] [#299](https://github.com/ShishirPatil/gorilla/pull/299): Leaderboard update with new models (`Claude-3-Haiku`, `Databrick-DBRX-Instruct`), more advanced AST evaluation procedure, and updated evaluation datasets. Cost and latency statistics during evaluation are also measured. We also released the manual that our evaluation procedure is based on, available [here](https://gorilla.cs.berkeley.edu/blogs/8_berkeley_function_calling_leaderboard.html#metrics).
- [Mar 11, 2024] [#254](https://github.com/ShishirPatil/gorilla/pull/254): Leaderboard update with 3 new models: `Claude-3-Opus-20240229 (Prompt)`, `Claude-3-Sonnet-20240229 (Prompt)`, and `meetkai/functionary-medium-v2.2 (FC)`
- [Mar 5, 2024] [#237](https://github.com/ShishirPatil/gorilla/pull/237) and [238](https://github.com/ShishirPatil/gorilla/pull/238): leaderboard update resulting from [#223](https://github.com/ShishirPatil/gorilla/pull/223); 3 new models: `mistral-large-2402`, `gemini-1.0-pro`, and `google/gemma-7b-it`.
- [Feb 29, 2024] [#223](https://github.com/ShishirPatil/gorilla/pull/223): modifications to REST evaluation.
