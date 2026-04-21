# Changes Since Commit `3b20786` (exclusive)

This document summarizes all work on the `hans-vision` branch from the commit *after*
`3b20786` through `HEAD` (currently `7d7b39958`). A total of **295 files** were
touched across **19 commits**.

## 1. Commit log

| Commit | Message |
|---|---|
| `7d7b39958` | 1 (`gemini.py` tweak) |
| `e8f666f4f` | fix zelle |
| `711099f2b` | delete id 175 |
| `0947b9662` | 1 |
| `58470cff6` | 1 |
| `dae9b9835` | 1 |
| `fae2a335c` | 1 |
| `05e059617` | 1 |
| `1cf1d97b8` | 1 |
| `6475c5e73` | Merge branch 'hans-vision' |
| `260415212` | update function doc and source code |
| `12db2aac0` | 1 |
| `bd9d681d5` | 1 |
| `87d058cac` | 1 |
| `7523d28c3` | Merge branch 'hans-vision' |
| `b3b1ca928` | 1 |
| `b97d34665` | update server initial config variant |
| `d20f08b5c` | 1 |
| `abef1feb3` | 1 |

## 2. High-level summary

The branch does three kinds of work:

1. **Failing-tools benchmark correctness pass** — renumber / reorganize
   `failing_tools.json`, delete one bad scenario, and make every
   `failure_injection.method` reference point at the renamed API methods in
   the multi-turn simulator source code.
2. **API surface cleanup** — rename methods in multiple `func_source_code/*.py`
   classes so that method names do not collide across APIs; propagate the new
   names into the public docs (`multi_turn_func_doc/*.json`), the failure patch
   files (`patches_*.py`), and `failing_tools.json`.
3. **Server state regeneration** — many `server_initial_config_variant/*.json`
   files are regenerated / compacted (most large diffs are pure regeneration,
   not logic bugs). Plus model-handler cleanup that removes several obsolete
   local-inference handlers and improves thread-safety of patch loading for the
   failing-tools runner.

## 3. Bugs fixed in the failing-tools benchmark

The failing-tools benchmark consists of three tightly coupled layers:

- test cases in `data/text/failing_tools.json`,
- ground-truth rubrics in `data/possible_answer/text/failing_tools.json`,
- injected failure decorators in `data/text/server_failure_patch/patches_*.py`,
- and the target method bodies in `eval_checker/multi_turn_eval/func_source_code/*.py`.

Changes in this branch fix bugs where these layers had fallen out of sync.

### 3.1 `failing_tools.json` was renumbered and the "extra" bucket eliminated

- **Before:** The file had scenarios `failing_tools_0` … `failing_tools_205`
  plus a separate bucket `failing_tools_extra_0` … `failing_tools_extra_19`
  (221 entries total). Two different numbering schemes in one file meant no
  single integer addressed scenarios, and IDs were jumbled after reorders.
- **After:** A single integer-indexed sequence covering IDs 0–219
  (220 entries). Commit `bd9d681d5` removed the `failing_tools_extra_*`
  entries; commits `12db2aac0` and `1cf1d97b8` renumbered / reordered them
  into the main numeric space (the 20 extras became new IDs `129–133` and
  `206–219`, i.e. 5 + 14 = 19 survivors).
- **`failing_tools_175` deletion (commit `711099f2b`)**: the scenario tied to
  `GmailAPI.create_filter` + `wrong_criteria` was dropped. The matching patch
  definition `create_filter_wrong_criteria` was also removed from
  `patches_gmail.py` so the patch registry no longer holds an orphan entry.

### 3.2 Method-rename drift between `failure_injection.method` and the API

In several places the failure-injection strings referenced method names that
no longer existed on the simulator class, which would have caused
`_apply_failure_injections` to fail at test time. These were fixed:

| API / class | Old name (broken reference) | New name (correct) | Files updated |
|---|---|---|---|
| `LyftAPI` | `get_trip_estimates` | `get_ride_estimates` | `failing_tools.json` IDs `_140`, `_147` (commit `58470cff6`) |
| `OutlookCalendarAPI` | `set_working_hours` | `configure_working_hours` | source `outlook_calendar.py`, `patches_outlook_calendar.py` S47 block, plus the failing-tools entry referencing the patch (commit `fae2a335c`) |
| `OutlookCalendarAPI` | `list_categories` | `list_event_categories` | source `outlook_calendar.py` (commit `fae2a335c`) — resolves the collision with `OutlookAPI.list_categories` |
| `WalmartAPI` | `get_basket` | `view_basket` | source `walmart.py` and the rename map in `scripts/apply_renames.py` (commit `fae2a335c`) |
| `VenmoAPI` | `create_split` | `create_group_payment` | `patches_venmo.py` (including patch decorator + helper fn name), plus the `failing_tools.json` entry referencing the patch (commit `0947b9662`) |
| `ZelleAPI` | `get_contacts` | `list_recipients` | `patches_zelle.py` (commit `0947b9662`) |

### 3.3 `ZelleAPI.list_recipients` patch shape mismatch (commit `0947b9662`)

`patches_zelle.py::list_recipients_stale_contacts` previously treated the
original return value as a `dict` of shape
`{"contacts": [...], "metadata": {...}}` and filtered `result["contacts"]`.
But `ZelleAPI.list_recipients` actually returns a **list** of contact dicts
directly. The patch has been rewritten to filter the list in place and
removed the synthetic `metadata.last_synced` field that no honest response
ever carries.

### 3.4 `ZelleAPI.check_recipient_enrolled` missing (commit `e8f666f4f`)

The Zelle failure-injection patch `check_recipient_enrolled / stale_enrollment`
targeted a method that did not exist on `ZelleAPI`, so applying the patch
would register a no-op and the corresponding failing-tools scenario couldn't
exercise the staleness recovery. The method was added to
`func_source_code/zelle.py` (~44 lines). It looks up a contact by email,
phone, or username and returns enrollment status, which is exactly what
the patch expects to corrupt.

### 3.5 `VenmoAPI.create_group_payment` docstring malformed (commit `05e059617`)

The old docstring for `participants` described the list contents as
free-form English ("List of participant dicts. Each dict must have
`contact_id`..."). That form is not understood by `_compile_helper.py`,
which generates the function-call schema exposed to the model.
The docstring was rewritten into the project's standard `List[Dict]` format
with dashed nested entries so the compiler emits proper
`items.properties` for the participants array.

### 3.6 `parse_docstring` didn't support `List[Dict]` (commit `05e059617`)

Companion to 3.5: `scripts/_compile_helper.py::parse_docstring` only
recognized nested dashed entries under a parent whose type was `dict`.
If a parent was `List[Dict]` (array-of-object), nested properties were
silently attached to the *previous* parent or lost. The parser was
extended so when the parent is an array whose items are dicts, nested
entries are written into `parent_entry["items"]["properties"]`. This is
what makes `VenmoAPI.create_group_payment`'s participants properly
schema-typed on both Claude / OpenAI tool-calling models.

### 3.7 Patch registry race condition in multi-threaded inference

`_load_all_server_patches()` was previously lazy and called from
`_apply_failure_injections()`, which runs per-worker in a thread pool.
Simultaneous loads could register the same patch twice or skip entries.
The fix:

- `_load_all_server_patches` was renamed to `load_all_server_patches`
  (public), and the lazy `_server_patches_loaded` guard was removed.
- `_llm_response_generation.generate_results` now calls
  `load_all_server_patches()` once on the main thread before dispatching
  workers, but only when the run includes a `failing_tools` category
  (gated by `is_failing_tools(category)`).

### 3.8 `apply_renames.py` missing `outlook_calendar` stems (commit `fae2a335c`)

The rename runner now knows that the file stem `outlook_calendar` maps to
class `OutlookCalendarAPI` and natural-language form `"Outlook Calendar"`, and
it carries the rename map `set_working_hours → configure_working_hours` and
`list_categories → list_event_categories`. Without this, re-running the
rename script would miss the Outlook Calendar dataset and drift would
reappear. The Walmart map entry was also flipped from
`get_cart → get_basket` to `get_cart → view_basket` to match 3.2.

## 4. Non-benchmark changes (summary)

- **`model_handler/` cleanup** (7 files deleted: `deepseek_reasoning.py`,
  `functiongemma.py`, `llama.py`, `llama_3_1.py`, `salesforce_llama.py`,
  `salesforce_qwen.py`; `kimi.py`, `openai_completion.py`, `utils.py`
  modified; small fixes in `claude.py`, `gemini.py`, `ling.py`, `writer.py`,
  `base_oss_handler.py`). Adds `handler.inference_request_extra_body`
  plumbing used by the new `build_handler` path.
- **`constants/model_config.py`**: large rewrite (~832 lines of diff), in
  line with the handler cleanup.
- **`utils.py`**: adds `query_contains_image_input(message)` helper and
  tightens `query_contains_audio_input` to reject simultaneous text content.
- **Multi-turn function docs** (`data/multi_turn_func_doc/*.json`, 30 files):
  regenerated from the renamed source so the model sees the current API.
- **Server initial-config variants** (`data/text/server_initial_config_variant/**`):
  regenerated state fixtures. Most diffs are pure whitespace / ordering
  changes from re-serialization; the `*/default.json` entries were also
  regenerated.

## 5. Full list of changed files (295)

### Benchmark (failing-tools) — core

- `berkeley-function-call-leaderboard/bfcl_eval/data/text/failing_tools.json`
- `berkeley-function-call-leaderboard/bfcl_eval/data/possible_answer/text/failing_tools.json`
- `berkeley-function-call-leaderboard/bfcl_eval/data/text/server_failure_patch/patches_gmail.py`
- `berkeley-function-call-leaderboard/bfcl_eval/data/text/server_failure_patch/patches_outlook_calendar.py`
- `berkeley-function-call-leaderboard/bfcl_eval/data/text/server_failure_patch/patches_venmo.py`
- `berkeley-function-call-leaderboard/bfcl_eval/data/text/server_failure_patch/patches_zelle.py`

### Benchmark (failing-tools) — runner / orchestration

- `berkeley-function-call-leaderboard/bfcl_eval/_llm_response_generation.py`
- `berkeley-function-call-leaderboard/bfcl_eval/eval_checker/multi_turn_eval/multi_turn_utils.py`
- `berkeley-function-call-leaderboard/bfcl_eval/scripts/_compile_helper.py`
- `berkeley-function-call-leaderboard/bfcl_eval/scripts/apply_renames.py`
- `berkeley-function-call-leaderboard/bfcl_eval/utils.py`

### Simulator classes (`func_source_code/*.py`, 28 files)

alpha_vantage, amazon, apple_music, booking, doordash, expedia, fidelity,
gmail, google_calendar, google_finance, google_map_review, instacart, lyft,
outlook, outlook_calendar, robinhood, spotify, target, uber, uber_eats,
vanguard, venmo, walmart, weather_com, yahoo_finance, yahoo_weather, yelp,
zelle.

### Function docs (`multi_turn_func_doc/*.json`, 30 files)

alpha_vantage, amazon, apple_music, booking, doordash, expedia, fidelity,
gmail, google_calendar, google_finance, google_map_review, instacart, lyft,
notion, outlook, outlook_calendar, robinhood, spotify, target, uber,
uber_eats, vanguard, venmo, walmart, weather_com, web_search, yahoo_finance,
yahoo_weather, yelp, zelle.

### Server initial-config variants (`server_initial_config_variant/**`, 211 files)

- **alpha_vantage** (3): default.json, empty.json, winter_travel.json
- **amazon** (4): catalog_daud.json, default.json, ghost_cart_daud.json, rachel_nespresso_027.json
- **apple_music** (5): apple_music_empty_library.json, apple_music_extra_library_tracks_and_playlists.json, apple_music_no_playback.json, apple_music_s68.json, default.json
- **booking** (13): bali_garden_villa_005.json, bali_garden_villa_010.json, barcelona_hostel_dorm_007.json, default.json, london_savoy_deluxe_011.json, london_savoy_king_004.json, paris_deluxe_basic_002.json, paris_deluxe_double_009.json, paris_deluxe_spa_001.json, paris_ritz_deluxe_006.json, paris_two_room_types_008.json, reservation_bk7m.json, rome_apartment_booked_003.json
- **confluence** (1): default.json
- **door_dash** (6): default.json, doordash.json, doordash_aisha_ramen_022.json, doordash_daud.json, doordash_extra_restaurants_and_menu_items.json, doordash_no_payment.json
- **expedia** (12): bali_garden_villa_005.json, bali_garden_villa_010.json, daud.json, default.json, london_savoy_deluxe_004.json, london_savoy_deluxe_011.json, paris_deluxe_double_009.json, paris_deluxe_spa_001.json, paris_ritz_deluxe_006.json, paris_superior_suite_008.json, paris_triple_room_002.json, rome_boutique_deluxe_003.json
- **fidelity** (3): account_f1.json, default.json, evan_aapl_021.json
- **gmail** (14): accountant_stale.json, aisha_empty_022.json, ava_empty_006_011.json, bigcorp_inbox.json, board_meeting_stale.json, booking_confirmation.json, contract_inbox.json, daud.json, default.json, hiking_thread.json, multi_turn_default.json, product_launch_thread.json, robinhood_stale.json, venmo_stale.json
- **google_calendar** (9): ava_empty_009_010_011.json, board_meeting.json, casey_empty_023.json, daud.json, default.json, personal.json, qbr_march.json, scheduling.json, team.json
- **google_finance** (3): default.json, empty.json, tech_growth.json
- **google_map_review** (26): artisan_bakery.json, austin_mexican.json, auto_body.json, auto_repair.json, boston_italian.json, breakfast_club.json, central_park.json, chicago_pharmacy.json, default.json, dental.json, diner_reviews.json, fine_dining.json, green_leaf_cafe.json, harbor_view.json, joes_pizza.json, multi_server.json, nashville_bbq.json, nyc_italian.json, quick_fix_auto.json, rooftop_bar.json, sakura.json, sf_coffee.json, sushi_zen.json, three_coffee.json, two_cafes.json, urban_grind.json
- **instacart** (6): atlanta_daud.json, checkout_daud.json, default.json, order_ic3m.json, saved_cart_daud.json, shared_daud.json
- **lyft** (10): default.json, jordan_high_fare_020.json, morgan_accord_standard_015.json, recent_ride.json, taylor_accord_on_trip_018.json, taylor_accord_standard_012.json, taylor_accord_standard_014.json, taylor_escalade_xl_013.json, taylor_escalade_xl_017.json, taylor_negative_fare_019.json
- **notion** (1): default.json
- **outlook** (8): accountant_full.json, bigcorp_inbox.json, board_meeting_full.json, daud.json, default.json, multi_turn_default.json, robinhood_full.json, venmo_full.json
- **outlook_calendar** (5): admin.json, daud.json, default.json, meetings.json, scheduling.json
- **robinhood** (3): account_nvda.json, default.json, evan_btc_aapl_021.json
- **spotify** (5): default.json, family_plan.json, spotify_evening_chill.json, spotify_extra_tracks_and_playlists.json, spotify_no_devices.json
- **target** (5): aisha_cart_pickup_026.json, aisha_nespresso_027.json, clean_checkout_daud.json, daud.json, default.json
- **uber** (7): active_ride_sfo_015.json, camry_lower_rating_018.json, camry_x_pool_016.json, camry_x_xl_014.json, camry_x_xl_020.json, default.json, suburban_x_xl_013.json
- **uber_eats** (4): default.json, order_ue6n.json, uber_eats_extra_restaurants_and_menu_items.json, ubereats_aisha_ramen_022.json
- **vanguard** (1): default.json
- **venmo** (6): daud.json, default.json, jordan_group_022.json, jordan_priya_020_027.json, morgan_priya_024.json, multi_turn_default.json
- **walmart** (5): catalog_daud.json, clean_checkout_daud.json, default.json, derek_grocery_pickup_025.json, order_wm4p.json
- **weather_com** (7): daud.json, default.json, denver.json, northeast.json, south.json, travel.json, west.json
- **yahoo_finance** (3): default.json, empty.json, renewable.json
- **yahoo_weather** (5): daud.json, default.json, south.json, travel.json, west.json
- **yelp** (26): artisan_bakery.json, austin_mexican.json, auto_body.json, auto_repair.json, boston_italian.json, breakfast_club.json, central_park.json, chicago_pharmacy.json, default.json, dental.json, diner_reviews.json, fine_dining.json, green_leaf_cafe.json, harbor_view.json, joes_pizza.json, multi_server.json, nashville_bbq.json, nyc_italian.json, quick_fix_auto.json, rooftop_bar.json, sakura.json, sf_coffee.json, sushi_zen.json, three_coffee.json, two_cafes.json, urban_grind.json
- **zelle** (5): default.json, jordan_priya_024.json, multi_turn_default.json, stale_contacts.json, stale_limit.json

### Model handler

- `berkeley-function-call-leaderboard/bfcl_eval/constants/model_config.py`
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/api_inference/claude.py`
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/api_inference/gemini.py`
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/api_inference/kimi.py`
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/api_inference/ling.py`
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/api_inference/openai_completion.py`
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/api_inference/writer.py`
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/local_inference/base_oss_handler.py`
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/local_inference/deepseek_reasoning.py` *(deleted)*
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/local_inference/functiongemma.py` *(deleted)*
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/local_inference/llama.py` *(deleted)*
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/local_inference/llama_3_1.py` *(deleted)*
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/local_inference/salesforce_llama.py` *(deleted)*
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/local_inference/salesforce_qwen.py` *(deleted)*
- `berkeley-function-call-leaderboard/bfcl_eval/model_handler/utils.py`
