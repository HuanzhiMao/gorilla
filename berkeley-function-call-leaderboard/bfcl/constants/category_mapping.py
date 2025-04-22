VERSION_PREFIX = "BFCL_v3"

# # These are in the PROMPT_PATH
# # Commented out ones are not used in the current version of benchmarking
# TEST_FILE_MAPPING = {
#     # V1 Non-Live Dataset
#     # "exec_simple": f"{VERSION_PREFIX}_exec_simple.json",
#     # "exec_parallel": f"{VERSION_PREFIX}_exec_parallel.json",
#     # "exec_multiple": f"{VERSION_PREFIX}_exec_multiple.json",
#     # "exec_parallel_multiple": f"{VERSION_PREFIX}_exec_parallel_multiple.json",
#     "simple": f"{VERSION_PREFIX}_simple.json",
#     "irrelevance": f"{VERSION_PREFIX}_irrelevance.json",
#     "parallel": f"{VERSION_PREFIX}_parallel.json",
#     "multiple": f"{VERSION_PREFIX}_multiple.json",
#     "parallel_multiple": f"{VERSION_PREFIX}_parallel_multiple.json",
#     "java": f"{VERSION_PREFIX}_java.json",
#     "javascript": f"{VERSION_PREFIX}_javascript.json",
#     # "rest": f"{VERSION_PREFIX}_rest.json",
#     # "sql": f"{VERSION_PREFIX}_sql.json",
#     # "chatable": f"{VERSION_PREFIX}_chatable.json",
#     # V2 Live Datasets
#     "live_simple": f"{VERSION_PREFIX}_live_simple.json",
#     "live_multiple": f"{VERSION_PREFIX}_live_multiple.json",
#     "live_parallel": f"{VERSION_PREFIX}_live_parallel.json",
#     "live_parallel_multiple": f"{VERSION_PREFIX}_live_parallel_multiple.json",
#     "live_irrelevance": f"{VERSION_PREFIX}_live_irrelevance.json",
#     "live_relevance": f"{VERSION_PREFIX}_live_relevance.json",
#     # V3 Multi-turn Datasets
#     "multi_turn_base": f"{VERSION_PREFIX}_multi_turn_base.json",
#     "multi_turn_miss_func": f"{VERSION_PREFIX}_multi_turn_miss_func.json",
#     "multi_turn_miss_param": f"{VERSION_PREFIX}_multi_turn_miss_param.json",
#     "multi_turn_long_context": f"{VERSION_PREFIX}_multi_turn_long_context.json",
#     # "multi_turn_composite": f"{VERSION_PREFIX}_multi_turn_composite.json",
#     # Agentic Datasets
#     "web_search": f"{VERSION_PREFIX}_web_search.json",
#     "web_search_conflict": f"{VERSION_PREFIX}_web_search_conflict.json",
#     "memory_student": f"{VERSION_PREFIX}_memory_student.json",
#     "memory_customer": f"{VERSION_PREFIX}_memory_customer.json",
#     "memory_finance": f"{VERSION_PREFIX}_memory_finance.json",
#     "memory_healthcare": f"{VERSION_PREFIX}_memory_healthcare.json",
#     "memory_notetaker": f"{VERSION_PREFIX}_memory_notetaker.json",
# }

NON_LIVE_CATEGORY = [
    "simple",
    "java",
    "javascript",
    "multiple",
    "parallel",
    "parallel_multiple",
    "irrelevance",
    # "exec_simple",
    # "exec_parallel",
    # "exec_multiple",
    # "exec_parallel_multiple",
    # "rest",
    # "sql",
    # "chatable",
]
LIVE_CATEGORY = [
    "live_simple",
    "live_multiple",
    "live_parallel",
    "live_parallel_multiple",
    "live_irrelevance",
    "live_relevance",
]
MULTI_TURN_CATEGORY = [
    "multi_turn_base",
    "multi_turn_miss_func",
    "multi_turn_miss_param",
    "multi_turn_long_context",
    # "multi_turn_composite",
]
WEB_SEARCH_CATEGORY = [
    "web_search",
    "web_search_conflict",
]
MEMORY_CATEGORY_BASE = [
    "memory_student",
    "memory_customer",
    "memory_finance",
    "memory_healthcare",
    "memory_notetaker",
]

SINGLE_TURN_CATEGORY = NON_LIVE_CATEGORY + LIVE_CATEGORY
AGENTIC_CATEGORY = MEMORY_CATEGORY + WEB_SEARCH_CATEGORY

ALL_CATEGORIES = SINGLE_TURN_CATEGORY + MULTI_TURN_CATEGORY + AGENTIC_CATEGORY

TEST_COLLECTION_MAPPING = {
    "all": ALL_CATEGORIES,
    "multi_turn": MULTI_TURN_CATEGORY,
    "single_turn": SINGLE_TURN_CATEGORY,
    "live": LIVE_CATEGORY,
    "non_live": NON_LIVE_CATEGORY,
    "non_python": [
        "java",
        "javascript",
    ],
    "python": [
        "simple",
        "irrelevance",
        "parallel",
        "multiple",
        "parallel_multiple",
        "live_simple",
        "live_multiple",
        "live_parallel",
        "live_parallel_multiple",
        "live_irrelevance",
        "live_relevance",
    ],
    # "web_search": WEB_SEARCH_CATEGORY,
    "memory": MEMORY_CATEGORY,
    "agentic": AGENTIC_CATEGORY,
}

MULTI_TURN_FUNC_DOC_FILE_MAPPING = {
    "GorillaFileSystem": "gorilla_file_system.json",
    "MathAPI": "math_api.json",
    "MessageAPI": "message_api.json",
    "TwitterAPI": "posting_api.json",
    "TicketAPI": "ticket_api.json",
    "TradingBot": "trading_bot.json",
    "TravelAPI": "travel_booking.json",
    "VehicleControlAPI": "vehicle_control.json",
    "WebSearchAPI": "web_search.json",
    "MemoryAPI_kv_store": "memory_api_kv.json",
    "MemoryAPI_vector_store": "memory_api_vector.json",
    "MemoryAPI_knowledge_graph": "memory_api_knowledge.json",
    "MemoryAPI_recursive_summary": "memory_api_recursive.json",
}

ALL_AVAILABLE_MEMORY_BACKENDS = [
    "kv_store",
    "vector_store",
    "recursive_summary",
    "knowledge_graph",
]
