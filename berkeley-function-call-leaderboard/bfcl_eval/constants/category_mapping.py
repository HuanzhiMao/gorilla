VERSION_PREFIX = "BFCL_v4"


#### Text Modality ####

TEXT_NON_LIVE_CATEGORY = [
    "text:simple_python",
    "text:simple_java",
    "text:simple_javascript",
    "text:multiple",
    "text:parallel",
    "text:parallel_multiple",
    "text:irrelevance",
    # "text:exec_simple",
    # "text:exec_parallel",
    # "text:exec_multiple",
    # "text:exec_parallel_multiple",
    # "text:rest",
    # "text:sql",
    # "text:chatable",
]
TEXT_LIVE_CATEGORY = [
    "text:live_simple",
    "text:live_multiple",
    "text:live_parallel",
    "text:live_parallel_multiple",
    "text:live_irrelevance",
    "text:live_relevance",
]
TEXT_MULTI_TURN_CATEGORY = [
    "text:multi_turn_base",
    "text:multi_turn_miss_func",
    "text:multi_turn_miss_param",
    "text:multi_turn_long_context",
    # "text:multi_turn_composite",
]
TEXT_WEB_SEARCH_CATEGORY = [
    "text:web_search_base",
    "text:web_search_no_snippet",
]

ALL_AVAILABLE_MEMORY_BACKENDS = [
    "kv",
    "vector",
    "rec_sum",
]
TEXT_MEMORY_CATEGORY = [
    f"text:memory_{backend}" for backend in ALL_AVAILABLE_MEMORY_BACKENDS
]
MEMORY_SCENARIO_NAME = [
    "student",
    "customer",
    "finance",
    "healthcare",
    "notetaker",
]

TEXT_SINGLE_TURN_CATEGORY = TEXT_NON_LIVE_CATEGORY + TEXT_LIVE_CATEGORY
TEXT_AGENTIC_CATEGORY = TEXT_MEMORY_CATEGORY + TEXT_WEB_SEARCH_CATEGORY
NON_SCORING_CATEGORY = ["text:format_sensitivity"]

#### Vision Modality ####

VISION_WEB_SEARCH_CATEGORY = [
    "vision:vision_web_search_base",
    "vision:vision_web_search_crop_169",
    "vision:vision_web_search_crop_43",
    "vision:vision_web_search_resize_169",
    "vision:vision_web_search_resize_43",
    "vision:vision_web_search_bw",
    "vision:vision_web_search_edge",
    "vision:vision_web_search_rg",
]

VISION_GEOGESSER_CATEGORY = [
    "vision:geogesser_type1",
    "vision:geogesser_type2",
    "vision:geogesser_type3",
]

#### True Audio Modality ####

# Audio reuses the same underlying tests as text, delivered via different modalities.
TRUE_AUDIO_NON_LIVE_CATEGORY = [
    cat.replace("text:", "true_audio:") for cat in TEXT_NON_LIVE_CATEGORY
]
TRUE_AUDIO_LIVE_CATEGORY = [
    cat.replace("text:", "true_audio:") for cat in TEXT_LIVE_CATEGORY
]
TRUE_AUDIO_SINGLE_TURN_CATEGORY = TRUE_AUDIO_NON_LIVE_CATEGORY + TRUE_AUDIO_LIVE_CATEGORY
TRUE_AUDIO_MULTI_TURN_CATEGORY = [
    cat.replace("text:", "true_audio:") for cat in TEXT_MULTI_TURN_CATEGORY
]

#### Text Audio Modality ####

TEXT_AUDIO_NON_LIVE_CATEGORY = [
    cat.replace("text:", "text_audio:") for cat in TEXT_NON_LIVE_CATEGORY
]
TEXT_AUDIO_LIVE_CATEGORY = [
    cat.replace("text:", "text_audio:") for cat in TEXT_LIVE_CATEGORY
]
TEXT_AUDIO_SINGLE_TURN_CATEGORY = TEXT_AUDIO_NON_LIVE_CATEGORY + TEXT_AUDIO_LIVE_CATEGORY
TEXT_AUDIO_MULTI_TURN_CATEGORY = [
    cat.replace("text:", "text_audio:") for cat in TEXT_MULTI_TURN_CATEGORY
]


#### Aggregate categories ####
ALL_TEXT_SCORING_CATEGORIES = (
    TEXT_SINGLE_TURN_CATEGORY + TEXT_MULTI_TURN_CATEGORY + TEXT_AGENTIC_CATEGORY
)
ALL_TEXT_CATEGORIES = ALL_TEXT_SCORING_CATEGORIES + NON_SCORING_CATEGORY
ALL_VISION_CATEGORY = VISION_WEB_SEARCH_CATEGORY + VISION_GEOGESSER_CATEGORY
ALL_TRUE_AUDIO_CATEGORY = TRUE_AUDIO_SINGLE_TURN_CATEGORY + TRUE_AUDIO_MULTI_TURN_CATEGORY
ALL_TEXT_AUDIO_CATEGORY = TEXT_AUDIO_SINGLE_TURN_CATEGORY + TEXT_AUDIO_MULTI_TURN_CATEGORY

ALL_MODALITY_SCORING_CATEGORIES = (
    ALL_TEXT_SCORING_CATEGORIES
    + ALL_TRUE_AUDIO_CATEGORY
    + ALL_TEXT_AUDIO_CATEGORY
    + ALL_VISION_CATEGORY
)
ALL_MODALITY_CATEGORIES = ALL_MODALITY_SCORING_CATEGORIES + NON_SCORING_CATEGORY

TEST_COLLECTION_MAPPING = {
    # Aggregate categories
    "all": ALL_MODALITY_CATEGORIES,
    "all_scoring": ALL_MODALITY_SCORING_CATEGORIES,
    "all_text": ALL_TEXT_CATEGORIES,
    "all_text_scoring": ALL_TEXT_SCORING_CATEGORIES,
    "all_true_audio": ALL_TRUE_AUDIO_CATEGORY,
    "all_text_audio": ALL_TEXT_AUDIO_CATEGORY,
    "all_vision": ALL_VISION_CATEGORY,
    # Text categories
    "text_non_live": TEXT_NON_LIVE_CATEGORY,
    "text_live": TEXT_LIVE_CATEGORY,
    "text_single_turn": TEXT_SINGLE_TURN_CATEGORY,
    "text_multi_turn": TEXT_MULTI_TURN_CATEGORY,
    "text_agentic": TEXT_AGENTIC_CATEGORY,
    "text_web_search": TEXT_WEB_SEARCH_CATEGORY,
    "text_memory": TEXT_MEMORY_CATEGORY,
    # Vision categories
    "vision_web_search": VISION_WEB_SEARCH_CATEGORY,
    "vision_geogesser": VISION_GEOGESSER_CATEGORY,
    # True Audio categories
    "true_audio_non_live": TRUE_AUDIO_NON_LIVE_CATEGORY,
    "true_audio_live": TRUE_AUDIO_LIVE_CATEGORY,
    "true_audio_single_turn": TRUE_AUDIO_SINGLE_TURN_CATEGORY,
    "true_audio_multi_turn": TRUE_AUDIO_MULTI_TURN_CATEGORY,
    # Text Audio categories
    "text_audio_non_live": TEXT_AUDIO_NON_LIVE_CATEGORY,
    "text_audio_live": TEXT_AUDIO_LIVE_CATEGORY,
    "text_audio_single_turn": TEXT_AUDIO_SINGLE_TURN_CATEGORY,
    "text_audio_multi_turn": TEXT_AUDIO_MULTI_TURN_CATEGORY,
}
