# Specifying Test Categories

Use modality-prefixed category names, such as `text:simple_python`,
`true_audio:multi_turn_base`, or `vision:geoguessr_type1`. The CLI accepts
comma-separated categories. Run `bfcl test-categories` for the complete collection
mapping.

## Collections

| Collection | Includes |
| --- | --- |
| `all` (default) | Every category, including the separately scored failing-tools suite |
| `all_scoring` | Every category included in leaderboard aggregation |
| `all_text`, `all_text_scoring` | Text categories, with or without failing tools |
| `all_true_audio` | Native audio versions of the 17 single-turn and multi-turn categories |
| `all_text_audio` | Matching ASR-text versions of those 17 categories |
| `all_vision` | Eight vision web-search variants and four GeoGuessr categories |
| `text:agentic`, `text:memory`, `text:web_search` | Text agentic subsets |
| `vision:web_search`, `vision:geoguessr` | Vision subsets |

The `non_live`, `live`, `single_turn`, and `multi_turn` collections are available
under each of `text:`, `true_audio:`, and `text_audio:`. Models are filtered by
capability before unsupported images or recordings are loaded. ASR-text input
does not require a native-audio-capable model.

## Individual categories

These base names are available under `text:`, `true_audio:`, and `text_audio:`:

- `simple_python`, `simple_java`, `simple_javascript`
- `multiple`, `parallel`, `parallel_multiple`, `irrelevance`
- `live_simple`, `live_multiple`, `live_parallel`, `live_parallel_multiple`,
  `live_irrelevance`, `live_relevance`
- `multi_turn_base`, `multi_turn_miss_func`, `multi_turn_miss_param`,
  `multi_turn_long_context`

Additional text categories are `text:web_search_base`,
`text:web_search_no_snippet`, `text:memory_kv`, `text:memory_vector`,
`text:memory_rec_sum`, and `text:failing_tools`. Failing tools receives its own
score file but has no overall leaderboard weight.

Vision web-search categories use the `vision:vision_web_search_` prefix followed
by `base`, `crop_169`, `crop_43`, `resize_169`, `resize_43`, `bw`, `edge`, or `rg`.
Each variant contains 250 questions with its corresponding image transformation.

GeoGuessr categories are `vision:geoguessr_type1` (80 questions),
`vision:geoguessr_type1_competition` (42), `vision:geoguessr_type2` (80), and
`vision:geoguessr_type3` (80). Type 1 and competition use distance scoring; types
2 and 3 use structured-answer matching. Configure `GEOGUESSR_SERVER_URL` to point
to the running GeoGuessr-Research server (default `http://127.0.0.1:18000`). Its
documented GCS server requires the panorama metadata database and image bucket.

## Audio variants and artifacts

`BFCL_AUDIO_VARIANT=noisy` is the default. Set it to `clean` for the clean baseline.
Native audio and ASR-text use the same selected recordings; ASR-text uses the
corresponding OpenAI ASR field already stored in the dataset. The loader never
substitutes the intended request for missing recognition output.

Use separate result and score directories for clean/noisy experiments, and keep
the same variant selected during generation and evaluation:

```bash
BFCL_AUDIO_VARIANT=noisy bfcl generate --model MODEL_NAME --test-category all_true_audio,all_text_audio --result-dir result_noisy
BFCL_AUDIO_VARIANT=noisy bfcl evaluate --model MODEL_NAME --test-category all_true_audio,all_text_audio --result-dir result_noisy --score-dir score_noisy
```

Audio results and score headers record their variant. Resume, partial overwrite,
evaluation, and leaderboard aggregation reject missing or conflicting variant
metadata. Older untagged audio results need regeneration. Full category overwrite
is available with `bfcl generate --allow-overwrite` (without `--run-ids`).

Clarification is supported when a message provides `clarifications` annotations.
The current audio corpus has none, so normal runs do not invoke the clarification
judge or synthesize answers to unannotated clarification questions.

## Evaluation and aggregation

`--partial-eval` works for all modalities, including vision and GeoGuessr. Prompts
and answers are matched to result IDs; duplicate and unknown IDs are rejected.

Vision Overall is the unweighted mean of all 12 registered vision categories,
including every web-search variant and GeoGuessr competition. Each category has
its own column in `score_vision_overall.csv`. Cross-modality Overall averages
Text, True Audio, Text Audio, and Vision. Missing categories remain `N/A` in their
individual columns and contribute zero to the corresponding overall scores.
