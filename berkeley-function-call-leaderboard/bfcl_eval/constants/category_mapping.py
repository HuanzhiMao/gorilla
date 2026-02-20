
VERSION_PREFIX = "BFCL_v4"

ALL_AVAILABLE_MEMORY_BACKENDS = [
    "kv",
    "vector",
    "rec_sum",
]

NON_LIVE_CATEGORY = [
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
LIVE_CATEGORY = [
    "text:live_simple",
    "text:live_multiple",
    "text:live_parallel",
    "text:live_parallel_multiple",
    "text:live_irrelevance",
    "text:live_relevance",
]
MULTI_TURN_CATEGORY = [
    "text:multi_turn_base",
    "text:multi_turn_miss_func",
    "text:multi_turn_miss_param",
    "text:multi_turn_long_context",
    # "text:multi_turn_composite",
]
WEB_SEARCH_CATEGORY = [
    "text:web_search_base",
    "text:web_search_no_snippet",
]
VISION_CATEGORY = [
    # "vision:vision_base",
    # @HuanzhiMao FIXME: uncomment these
    # "vision:vision_crop_169",
    # "vision:vision_crop_43",
    # "vision:vision_resize_169",
    # "vision:vision_resize_43",
    # "vision:vision_bw",
    # "vision:vision_edge",
    # "vision:vision_rg",
    "vision:geogesser_type1",
    "vision:geogesser_type2",
    "vision:geogesser_type3",
]

MEMORY_CATEGORY = [f"text:memory_{backend}" for backend in ALL_AVAILABLE_MEMORY_BACKENDS]
MEMORY_SCENARIO_NAME = [
    "student",
    "customer",
    "finance",
    "healthcare",
    "notetaker",
]


SINGLE_TURN_CATEGORY = NON_LIVE_CATEGORY + LIVE_CATEGORY
AGENTIC_CATEGORY = MEMORY_CATEGORY + WEB_SEARCH_CATEGORY
NON_SCORING_CATEGORY = ["text:format_sensitivity"]

# Audio reuses the same underlying tests as text, delivered via different modalities.
AUDIO_CATEGORY = [
    cat.replace("text:", "true_audio:")
    for cat in SINGLE_TURN_CATEGORY + MULTI_TURN_CATEGORY
]
AUDIO_TRANSCRIPT_CATEGORY = [
    cat.replace("text:", "text_audio:")
    for cat in SINGLE_TURN_CATEGORY + MULTI_TURN_CATEGORY
]

ALL_SCORING_CATEGORIES = (
    SINGLE_TURN_CATEGORY
    + MULTI_TURN_CATEGORY
    + AGENTIC_CATEGORY
    + VISION_CATEGORY
    + AUDIO_CATEGORY
    + AUDIO_TRANSCRIPT_CATEGORY
)
ALL_CATEGORIES = ALL_SCORING_CATEGORIES + NON_SCORING_CATEGORY

TEST_COLLECTION_MAPPING = {
    "all": ALL_CATEGORIES,
    "all_scoring": ALL_SCORING_CATEGORIES,
    "multi_turn": MULTI_TURN_CATEGORY,
    "single_turn": SINGLE_TURN_CATEGORY,
    "live": LIVE_CATEGORY,
    "non_live": NON_LIVE_CATEGORY,
    "non_python": [
        "text:simple_java",
        "text:simple_javascript",
    ],
    "python": [
        "text:simple_python",
        "text:irrelevance",
        "text:parallel",
        "text:multiple",
        "text:parallel_multiple",
        "text:live_simple",
        "text:live_multiple",
        "text:live_parallel",
        "text:live_parallel_multiple",
        "text:live_irrelevance",
        "text:live_relevance",
    ],
    "memory": MEMORY_CATEGORY,
    "web_search": WEB_SEARCH_CATEGORY,
    "agentic": AGENTIC_CATEGORY,
    "vision": VISION_CATEGORY,
    "true_audio": AUDIO_CATEGORY,
    "text_audio": AUDIO_TRANSCRIPT_CATEGORY,
}
