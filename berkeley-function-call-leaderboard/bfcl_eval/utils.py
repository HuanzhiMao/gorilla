import base64
import hashlib
import json
import logging
import os
import re
from copy import deepcopy
from pathlib import Path
from threading import Lock
from typing import Union

from bfcl_eval.constants.category_mapping import *
from bfcl_eval.constants.default_prompts import (
    ADDITIONAL_SYSTEM_PROMPT_FOR_AGENTIC_RESPONSE_FORMAT,
    DEFAULT_SYSTEM_PROMPT_FORMAT,
    SYSTEM_PROMPT_FOR_AUDIO_AGENT,
)
from bfcl_eval.constants.eval_config import *
from bfcl_eval.constants.executable_backend_config import (
    MULTI_TURN_FUNC_DOC_FILE_MAPPING,
    UPDATED_TOOL_LIST_CLASSES,
)
from bfcl_eval.constants.enums import Modality
from filelock import FileLock

_FILE_LOCK_REGISTRY: dict[str, FileLock] = {}
_FILE_LOCK_REGISTRY_LOCK = Lock()


def _get_file_lock(filepath: str) -> FileLock:
    """
    Get a file lock for a given file path.
    This function returns a cross-process file lock (using the `filelock` library) to prevent multiple
    processes or threads from writing to the same target file at the same time. All lock files are
    colocated in the hidden directory `LOCK_DIR` so they don’t clutter the actual data folders.
    """
    digest = hashlib.sha1(os.path.abspath(filepath).encode()).hexdigest()
    lock_path = str(LOCK_DIR / f"{digest}.lock")
    with _FILE_LOCK_REGISTRY_LOCK:
        lock = _FILE_LOCK_REGISTRY.get(lock_path)
        if lock is None:
            # Each file has its own lock file on disk; FileLock ensures cross-process exclusivity.
            lock = FileLock(lock_path)
            _FILE_LOCK_REGISTRY[lock_path] = lock
        return lock


def sanitize_model_name_for_path(model_name: str) -> str:
    """Replace characters that are invalid in file/directory names with underscores.

    Handles forward slashes (Unix path separator), backslashes (Windows path
    separator), and other characters that are forbidden on Windows
    (< > : " | ? *).
    """
    return re.compile(r'[<>:"/\\|?*]').sub("_", model_name)


#### Helper functions to extract/parse/complete test category from different formats ####

# Category names use the format "modality:base_name", e.g. "text:simple_python",
# "vision:geoguessr_type1", "true_audio:simple_python", "text_audio:simple_python".
# File names do NOT include the modality prefix — the directory structure handles it.


# @HuanzhiMao FIXME: remove extra safety check
def parse_full_category(full_category: str) -> tuple[Modality, str]:
    """Parse a modality-prefixed category into (modality, base_name).

    Example: "text:simple_python" → (Modality.TEXT, "simple_python")
    """
    assert (
        ":" in full_category
    ), f"Category {full_category} is not a modality-prefixed category."
    modality, _, base_category = full_category.partition(":")
    return Modality(modality), base_category


def get_base_category(full_category: str) -> str:
    """Strip the modality prefix from a category name.

    Example: "text:simple_python" → "simple_python"
    """
    assert (
        ":" in full_category
    ), f"Category {full_category} is not a modality-prefixed category."
    modality, _, base_category = full_category.partition(":")
    assert (
        modality in Modality._value2member_map_
    ), f"Modality {modality} is not a valid modality."
    return base_category


def get_category_modality(full_category: str) -> Modality:
    """Extract the modality from a prefixed category name.

    Example: "text:simple_python" → Modality.TEXT
    """
    modality = Modality(full_category.split(":")[0])
    return modality


def extract_test_category(input_string: Union[str, Path], raise_error: bool = True) -> str:
    """
    Extract the test category from a given file name. If category cannot be extracted, and the flag is not set, then raise an error.
    """
    input_string = Path(input_string).name
    pattern = r"^(\w+?)(?:_score|_result)?\.json$"
    match = re.search(pattern, input_string)

    # Check if there's a match and extract the captured group
    if match:
        return match.group(1)  # the first captured group (\w+)
    elif raise_error:
        raise ValueError(
            f"Could not extract the test category from the input string: {input_string}"
        )
    else:
        return None


def extract_test_category_from_id(test_entry_id: str, remove_prereq: bool = False) -> str:
    """
    Extract the test category (including modality prefix) from the test entry ID.

    Examples:
        "text:simple_python_5" → "text:simple_python"
        "text:format_sensitivity_0|prompt_config|text:live_simple_23" → "text:format_sensitivity"
        "text:memory_kv_prereq_0" (without remove_prereq=True) → "text:memory_kv_prereq"
        "text:memory_kv_prereq_0" (with remove_prereq=True) → "text:memory_kv"

    If `remove_prereq` is True, it will remove the "_prereq" suffix from the test category,
    only relevant for memory test categories.
    """
    if remove_prereq:
        test_entry_id = test_entry_id.replace("_prereq", "")
    # Format sensitivity IDs use "|" as separator:
    # Example: "text:format_sensitivity_0|prompt_config|text:live_simple_23"
    if "|" in test_entry_id:
        test_entry_id = test_entry_id.split("|")[0]
    return test_entry_id.rsplit("_", 1)[0]


def extract_prompt_format_from_id(test_entry_id: str) -> str:
    """
    Extract the prompt format from the test entry ID.
    Format sensitivity IDs use "|" as separator.
    Example: "text:format_sensitivity_0|prompt_config|text:live_simple_23" → "prompt_config"
    """
    if "|" not in test_entry_id:
        return DEFAULT_SYSTEM_PROMPT_FORMAT
    else:
        # @HuanzhiMao doublecheck
        assert (
            len(test_entry_id.split("|")) == 2
        ), f"Test entry ID {test_entry_id} should contain exactly two pipes, since they are supposed to be the format sensitivity ids."
        return test_entry_id.split("|")[1]


def extract_memory_backend_type(test_category):
    """
    This function extracts the memory backend type from the test category.
    The test category should be in the form of `text:memory_kv` or `text:memory_vector`, etc.
    """
    if not is_memory(test_category):
        raise ValueError(f"Test category {test_category} is not a memory category.")

    return test_category.split("memory_")[1]


def find_file_by_category(
    test_category: str,
    folder_path: Path,
    is_result_file: bool = False,
    is_score_file: bool = False,
) -> Path:
    """
    Find a JSON file in the specified folder that matches the given test category.
    By default, it looks for a file with the suffix ".json".
    If `is_result_file` is True, it looks for a file with the suffix "_result.json".
    If `is_score_file` is True, it looks for a file with the suffix "_score.json".
    """
    assert not (is_result_file and is_score_file), "Cannot be both result and score file."

    if is_result_file:
        suffix = "_result.json"
    elif is_score_file:
        suffix = "_score.json"
    else:
        suffix = ".json"

    for json_file in folder_path.rglob(f"*{suffix}"):
        if extract_test_category(json_file, raise_error=False) == test_category:
            return json_file
    raise FileNotFoundError(f"No JSON file found with category: {test_category}")


def get_file_name_by_category(
    test_category: str,
    is_result_file: bool = False,
    is_score_file: bool = False,
) -> str:
    """
    Get the file name for a given test category.
    Uses the base category name (without modality prefix) for the file name,
    since modality is encoded in the directory structure, not the file name.
    """
    assert not (is_result_file and is_score_file), "Cannot be both result and score file."

    base_category = get_base_category(test_category)

    if is_result_file:
        file_name = f"{base_category}_result.json"
    elif is_score_file:
        file_name = f"{base_category}_score.json"
    else:
        file_name = f"{base_category}.json"

    return file_name


def parse_test_category_argument(test_category_args: list[str]) -> list[str]:
    test_name_total = set()

    for test_category in test_category_args:
        if test_category in TEST_COLLECTION_MAPPING:
            for test_name in TEST_COLLECTION_MAPPING[test_category]:
                test_name_total.add(test_name)
        elif test_category in ALL_MODALITY_CATEGORIES:
            test_name_total.add(test_category)
        else:
            # Invalid test category name
            raise Exception(f"Invalid test category name provided: {test_category}")

    return sorted(list(test_name_total))


def load_test_entries_from_id_file(id_file_path: Path) -> tuple[list[str], list[dict]]:
    """
    Helper function to load the test entries from the id file (e.g. `test_case_ids_to_generate.json.example`)
    """
    with open(id_file_path) as f:
        test_ids_to_generate = json.load(f)

    categories: list[str] = []
    entries: list[dict] = []
    for category, test_ids in test_ids_to_generate.items():
        # Skip categories that have an empty ID list
        if not test_ids:
            continue
        # Extend the entries list with only those whose id is present in the ID list
        entries.extend(
            [entry for entry in load_dataset_entry(category) if entry["id"] in test_ids]
        )
        categories.append(category)

    return categories, entries


#### Predicate functions to check the test category ####


def is_true_audio(test_category):
    return "audio" in test_category


def is_text_audio(test_category):
    return "text_audio" in test_category


def contain_native_audio_input(test_category):
    """
    Check if the test category requires a native audio input.
    """
    return is_true_audio(test_category)


def could_allow_clarification(test_category):
    """
    Check if the test category allows the model to ask for clarification.
    Only audio tasks (true_audio and text_audio) allow clarification.
    """
    return is_true_audio(test_category)


def is_vision_web_search(test_category: str) -> bool:
    """
    Check if the test category is a vision web search category (eg, vision_web_search_base, vision_web_search_rg, etc.).
    """
    return "vision_web_search" in test_category


def is_geoguessr(test_category: str) -> bool:
    return "geoguessr" in test_category


# @HuanzhiMao TODO: find a better name?
# Used for checker, because type 1 has a different metric than the rest of the categories.
def is_geoguessr_type1(test_category: str) -> bool:
    return is_geoguessr(test_category) and "type1" in test_category


def contain_vision_input(test_category: str) -> bool:
    """
    Check if the test category requires a vision input (eg, vision_web_search_base, geoguessr_type1, etc.).
    """
    return is_vision_web_search(test_category) or is_geoguessr(test_category)


def is_vision(test_category: str) -> bool:
    return is_vision_web_search(test_category) or is_geoguessr(test_category)


def is_format_sensitivity(test_category: str) -> bool:
    return "format_sensitivity" in test_category


# @HuanzhiMao TODO: rename this?
def is_web_search(test_category):
    return "web_search" in test_category and not is_vision_web_search(test_category)


def is_memory(test_category):
    return "memory" in test_category


def is_first_memory_prereq_entry(test_entry_id):
    return "prereq" in test_entry_id and test_entry_id.endswith("-0")


def is_memory_prereq(test_category):
    return "prereq" in test_category


def is_agentic(test_category):
    return "web_search" in test_category or "memory" in test_category


def is_multi_turn(test_category):
    return "multi_turn" in test_category


def is_live(test_category):
    return "live" in test_category


def is_non_live(test_category: str) -> bool:
    # Be careful that format sensitivity entry id are in the format of "format_sensitivity_0:prompt_format:live_simple_23-5-1", which might be misclassified if not checked first
    return not any(
        (
            is_format_sensitivity(test_category),
            is_live(test_category),
            is_multi_turn(test_category),
            is_agentic(test_category),
        )
    )


def contain_multi_turn_irrelevance(test_category):
    return "miss_func" in test_category or "miss_param" in test_category


def is_executable(test_category):
    return "exec" in test_category or "rest" in test_category


def is_rest(test_category):
    return "rest" in test_category


def is_relevance_or_irrelevance(test_category):
    return "relevance" in test_category or "irrelevance" in test_category


def is_chatable(test_category):
    return "chatable" in test_category


def is_java(test_category):
    return "java" in test_category and not is_js(test_category)


def is_js(test_category):
    return "javascript" in test_category


def is_sql(test_category):
    return "sql" in test_category

def is_failing_tools(test_category):
    return "failing_tools" in test_category


def contain_multi_step_interaction(test_category):
    return (
        is_multi_turn(test_category)
        or is_agentic(test_category)
        or contain_vision_input(test_category)
        or is_failing_tools(test_category)
    )


def get_directory_structure_by_id(test_id: str) -> str:
    """
    Get the modality directory for result/score files for a test entry.
    Extracts the modality prefix from the test entry ID.
    """
    return get_category_modality(test_id).value


def get_directory_structure_by_category(test_category: str) -> str:
    """
    Get the modality directory for result/score files for a test category.
    """
    return get_category_modality(test_category).value


def detect_modality_from_path(file_path: Path, model_dir: Path) -> str:
    """
    Detect the modality from a result/score file's parent directory.
    e.g., model_dir/text_audio/simple_python_result.json → 'text_audio'
    """
    relative = file_path.relative_to(model_dir)
    return relative.parts[0]


def get_memory_artifact_dir_by_id(test_id: str) -> str:
    """
    Get the directory for memory artifacts (snapshots, pre-req checkpoints) for a test entry.
    Returns a path like "text/_memory_artifacts/kv".
    """
    return get_memory_artifact_dir_by_category(extract_test_category_from_id(test_id))


def get_memory_artifact_dir_by_category(test_category: str) -> str:
    """
    Get the directory for memory artifacts (snapshots, pre-req checkpoints) for a test category.
    Returns a path like "text/_memory_artifacts/kv".
    """
    dir_structure = get_directory_structure_by_category(test_category)
    backend_type = extract_memory_backend_type(test_category)
    return os.path.join(dir_structure, "_memory_artifacts", backend_type)


#### Helper functions to load/write the dataset files ####


def load_file(file_path, sort_by_id: bool = False, use_lock: bool = True) -> list[dict]:
    result = []

    def _load_entries(input_path: str) -> None:
        with open(input_path) as f:
            file = f.readlines()
            for line in file:
                content = json.loads(line)
                result.append(content)

    if use_lock:
        with _get_file_lock(file_path):
            _load_entries(file_path)
    else:
        _load_entries(file_path)

    if sort_by_id:
        result.sort(key=sort_key)
    return result


def sort_file_content_by_id(file_path: Path) -> None:
    """
    Sort the content of a file by the id of the entries. The file is only rewritten
    when the ordering actually changes to avoid unnecessary disk writes.
    """
    # Acquire the lock for the entire critical section
    with _get_file_lock(file_path):
        # Load the current content preserving original order (and potential duplicates)
        original_entries = load_file(file_path, use_lock=False)

        # Desired final ordering (sorted, unique)
        sorted_entries = sorted(original_entries, key=sort_key)

        assert len(original_entries) == len(
            sorted_entries
        ), "There should be no duplicates in the file"

        # Check if the write is necessary by comparing id sequences
        original_ids = [entry["id"] for entry in original_entries]
        sorted_ids = [entry["id"] for entry in sorted_entries]

        if original_ids != sorted_ids:
            # We already have the lock, so we don't need to acquire it again
            write_list_of_dicts_to_file(file_path, sorted_entries, use_lock=False)


def load_dataset_entry(
    test_category: str,
    include_prereq: bool = True,
    include_language_specific_hint: bool = True,
) -> list[dict]:
    """
    This function retrieves the dataset entry for a given test category.
    The test_category must be a modality-prefixed category (e.g., "text:simple_python").
    File paths use the base category name; entry IDs are prefixed with the modality at the end.
    """
    modality = get_category_modality(test_category)
    base_category = get_base_category(test_category)
    modality_path = MODALITY_DATASET_PATH[modality]

    if modality in [Modality.TRUE_AUDIO, Modality.TEXT_AUDIO]:
        # True Audio or Text Audio categories
        all_entries = load_file(modality_path / f"{base_category}.json")
        all_entries = process_audio_test_case(all_entries, modality=modality)

    elif modality is Modality.VISION:
        if is_vision_web_search(test_category):
            # Vision Web Search categories
            # All categories share the same prompt file
            all_entries = load_file(modality_path / "vision_web_search_base.json")
            all_entries = process_vision_web_search_test_cases(all_entries, base_category)

        elif is_geoguessr(test_category):
            # geoguessr categories
            all_entries = load_file(modality_path / f"{base_category}.json")
            all_entries = process_geoguessr_test_case(all_entries)
        else:
            raise ValueError(f"Invalid vision category: {test_category}")

    else:
        assert modality is Modality.TEXT, f"Invalid modality: {modality}"
        # Text categories

        if is_format_sensitivity(test_category):
            # Format sensitivity categories
            all_entries = load_format_sensitivity_test_cases()

        elif is_web_search(test_category):
            # Web search categories
            all_entries = load_file(modality_path / "web_search.json")
            all_entries = process_web_search_test_case(all_entries, base_category)

        elif is_memory(test_category):
            # Memory categories
            # pass base category so ID replacements stay prefix-free
            all_entries = load_file(modality_path / "memory.json")
            for scenario in MEMORY_SCENARIO_NAME:
                all_entries = process_memory_test_case(
                    all_entries, base_category, scenario, include_prereq=include_prereq
                )

        else:
            # All other categories, we don't need any special handling
            all_entries = load_file(modality_path / f"{base_category}.json")

    all_entries = resolve_initial_config_file_paths(all_entries, SERVER_INITIAL_CONFIG_VARIANT_PATH)
    all_entries = process_agentic_test_case(all_entries)
    all_entries = populate_test_cases_with_predefined_functions(all_entries)

    if include_language_specific_hint:
        all_entries = add_language_specific_hint_to_function_doc(all_entries)

    # Prefix all entry IDs with the modality
    for entry in all_entries:
        entry["id"] = f"{modality.value}:{entry['id']}"

    return all_entries


def load_ground_truth_entry(test_category: str) -> list[dict]:
    """
    This function retrieves the ground truth entry for a given test category.
    The test_category must be a modality-prefixed category (e.g., "text:simple_python").
    Entry IDs are prefixed with the modality to match the corresponding dataset entries.

    Audio modalities (true_audio, text_audio) share the same ground truth files as
    text, so we load from the text ground truth directory.

    Vision modalities use their own ground truth directory. Vision web search
    categories all share the ``vision_base.json`` ground truth file, while
    geoguessr categories each have their own file.
    """
    modality = get_category_modality(test_category)
    base_category = get_base_category(test_category)

    if is_format_sensitivity(test_category):
        # Format sensitivity ground truth handles its own ID construction;
        # it calls load_ground_truth_entry() for inner categories which already prefix.
        return load_format_sensitivity_ground_truth_entry()

    # Audio modalities reuse the text ground truth files.
    if modality in (Modality.TRUE_AUDIO, Modality.TEXT_AUDIO):
        ground_truth_dir = MODALITY_POSSIBLE_ANSWER_PATH[Modality.TEXT]
    else:
        ground_truth_dir = MODALITY_POSSIBLE_ANSWER_PATH[modality]

    # Vision web search categories all share the vision_base ground truth.
    if is_vision_web_search(test_category):
        entries = load_file(ground_truth_dir / "vision_base.json")

    elif is_memory(test_category):
        entries = load_file(ground_truth_dir / "memory.json")

    elif is_web_search(test_category):
        entries = load_file(ground_truth_dir / "web_search.json")

    else:
        entries = load_file(ground_truth_dir / f"{base_category}.json")

    # Prefix all entry IDs with the modality to match dataset entries
    for entry in entries:
        if "id" in entry:
            entry["id"] = f"{modality}:{entry['id']}"

    return entries


def write_list_of_dicts_to_file(filename, data, subdir=None, use_lock: bool = True) -> None:
    """
    Write a list of dictionaries to a file.
    If `subdir` is provided, the file will be written to the subdirectory.
    """
    if subdir:
        # Ensure the (possibly nested) subdirectory exists
        os.makedirs(subdir, exist_ok=True)

        # Construct the full path to the file
        filename = os.path.join(subdir, os.path.basename(filename))

    abs_filename = os.path.abspath(filename)

    def _write_entries(output_path: str):
        """Internal helper that performs the actual write operation."""
        with open(output_path, "w", encoding="utf-8") as f:
            for i, entry in enumerate(data):
                # Go through each key-value pair in the dictionary to make sure the values are JSON serializable
                entry = make_json_serializable(entry)
                json_str = json.dumps(entry, ensure_ascii=False) + "\n"
                f.write(json_str)

    if use_lock:
        with _get_file_lock(abs_filename):
            _write_entries(abs_filename)
    else:
        _write_entries(abs_filename)


def make_json_serializable(value):
    if isinstance(value, dict):
        # If the value is a dictionary, we need to go through each key-value pair recursively
        return {k: make_json_serializable(v) for k, v in value.items()}
    elif isinstance(value, list):
        # If the value is a list, we need to process each element recursively
        return [make_json_serializable(item) for item in value]
    else:
        # Try to serialize the value directly, and if it fails, convert it to a string
        try:
            json.dumps(value, ensure_ascii=False)
            return value
        except (TypeError, ValueError):
            return str(value)


def sort_key(entry):
    """
    Index comes in two forms: TestCategory_Index or TestCategory_Index-FuncDocSubIndex-PromptSubIndex; both 0-indexed.

    TestCategory_Index: For example, `simple_20` means the 21st entry in the `simple` test category.

    TestCategory_Index-FuncDocSubIndex-PromptSubIndex is used when there are multiple prompts for a single function doc; this only happens in the live dataset.
    FuncDocSubIndex increments for each unique function doc.
    PromptSubIndex is per function doc. It resets to 0 for each function doc.
        For example, `live_simple_19-3-15` means the 20th entry in the `live_simple` test category.
        This entry has the 4th unique function doc and the 16th prompt for that function doc (there are at least 15 other prompts for this same function doc in this category).

    In either case, the universal index is enough to sort the entries.
    """
    entry_id = entry["id"].split(":")[-1]
    parts = entry_id.rsplit("_", 1)
    test_category, index = parts[0], parts[1]
    # This handles the case where the index is in the form TestCategory_Index-FuncDocSubIndex-PromptSubIndex
    if "-" in index:
        assert index.count("-") == 2, f"Invalid index format: {index}"
        index = index.split("-")[0]

    # Make sure the memory prereq entries are inferenced first to avoid the memory entries being blocked due to dependencies.

    # Memory prereq happen first
    if is_memory_prereq(test_category):
        priority = 0
    # Web search happen second
    elif is_web_search(test_category):
        priority = 1
    # Single-turn happen third
    elif not contain_multi_step_interaction(test_category):
        priority = 2
    # Multi-turn happen fourth
    elif is_multi_turn(test_category):
        priority = 3
    # Memory happen last
    # Hopefully the prereq entries are done by now
    elif is_memory(test_category):
        priority = 4
    elif contain_vision_input(test_category):
        priority = 5
    elif is_failing_tools(test_category):
        priority = 6

    return (priority, test_category, int(index))


def filter_entries_by_id(
    reference_entries: list[dict],
    candidate_entries: list[dict],
) -> list[dict]:
    """
    Return all entries in `candidate_entries` whose ``"id"`` *matches*
    at least one entry in `reference_entries`.
    """

    reference_ids = {entry["id"] for entry in reference_entries}
    return [entry for entry in candidate_entries if entry["id"] in reference_ids]


def update_available_tool_list_in_test_case(
    test_entry: dict, involved_instances: dict
) -> dict:
    """
    Update the available tool list in the test entry.
    """

    for class_name, class_instance in involved_instances.items():
        if class_name in UPDATED_TOOL_LIST_CLASSES:
            assert hasattr(class_instance, "_get_updated_tool_list") and callable(
                getattr(class_instance, "_get_updated_tool_list")
            )
            available_tool_names = class_instance._get_updated_tool_list()
            backend_func_docs = load_file(
                MULTI_TURN_FUNC_DOC_PATH / MULTI_TURN_FUNC_DOC_FILE_MAPPING[class_name]
            )

            # Get all tool names for this backend
            backend_tool_names = {tool["name"] for tool in backend_func_docs}

            # Remove all tools tied to this backend from test_entry["function"]
            test_entry["function"] = [
                tool
                for tool in test_entry["function"]
                if tool["name"] not in backend_tool_names
            ]

            # Add back only the tools that are still available (name exists in updated_tool_list)
            updated_tool_docs = [
                tool for tool in backend_func_docs if tool["name"] in available_tool_names
            ]
            test_entry["function"].extend(updated_tool_docs)

    return test_entry


#### Helper functions to check the output format ####


# TODO: Reorganize this function to be more readable
def is_function_calling_format_output(decoded_output):
    """
    Ensure the output is a list of dictionaries of the form:
    `[{func1: {param1: val1, param2: val2, ...}}, {func2: {param1: val1, param2: val2, ...}}, ...]`
    Sometimes the model handler's `decode_ast` method will return successfully, but the output is not in the correct format, and that will mess up the downstream evaluation that expects this format.
    This is especially the case when the model doesn't predict any function calls, and the output is an human-readable string.
    Note: Empty list `[]` is considered the correct format in this check.
    """
    if type(decoded_output) != list:
        return False
    for item in decoded_output:
        if type(item) != dict:
            return False
        # Check for `{func1: {param1: val1, param2: val2, ...}}`, should only have one key-value pair
        if len(item) != 1:
            return False
        # Check for `{param1: val1, param2: val2, ...}`; the parameter-value pairs should be a dictionary
        if type(list(item.values())[0]) != dict:
            return False
    return True


# TODO: Runner should use this function to check for format first
def is_executable_format_output(decoded_output):
    # Ensure the output is a list of strings (one or more strings)
    if type(decoded_output) == list:
        if len(decoded_output) == 0:
            return False
        for item in decoded_output:
            if type(item) != str:
                return False
        return True
    return False


def is_empty_output(decoded_output):
    # This function is a patch to the ast decoder for relevance detection
    # Sometimes the ast decoder will parse successfully, but the input doens't really have a function call
    # [], [{}], and anything that is not in function calling format is considered empty (and thus should be marked as correct)
    if not is_function_calling_format_output(decoded_output):
        return True
    if len(decoded_output) == 0:
        return True
    if len(decoded_output) == 1 and len(decoded_output[0]) == 0:
        return True
    return False


#### Helper functions to process the dataset entries ####


def _get_language_specific_hint(test_category):
    if test_category == "java":
        return " Note that the provided function is in Java 8 SDK syntax."
    elif test_category == "javascript":
        return " Note that the provided function is in JavaScript syntax."
    else:
        return " Note that the provided function is in Python 3 syntax."


def _func_doc_language_specific_pre_processing(
    function: list[dict], test_category: str
) -> list[dict]:
    if len(function) == 0:
        return function

    assert type(function) == list
    for item in function:
        # Add language specific hints to the function description
        item["description"] = item["description"] + _get_language_specific_hint(
            test_category
        )
        # Process the parameters
        properties = item["parameters"]["properties"]
        if is_java(test_category):
            for key, value in properties.items():
                if value["type"] == "any":
                    properties[key][
                        "description"
                    ] += " This parameter can be of any type of Java object in string representation."
                else:
                    value[
                        "description"
                    ] += f" This is Java {value['type']} type parameter in string representation."
                if value["type"] == "ArrayList" or value["type"] == "Array":
                    value[
                        "description"
                    ] += f" The list elements are of type {value['items']['type']}; they are not in string representation."
                    del value["items"]

                value["type"] = "string"

        elif is_js(test_category):
            for key, value in properties.items():
                if value["type"] == "any":
                    properties[key][
                        "description"
                    ] += " This parameter can be of any type of JavaScript object in string representation."
                else:
                    value[
                        "description"
                    ] += f" This is JavaScript {value['type']} type parameter in string representation."
                if value["type"] == "array":
                    value[
                        "description"
                    ] += f" The list elements are of type {value['items']['type']}; they are not in string representation."
                    del value["items"]

                if value["type"] == "dict":
                    if "properties" in value:  # not every dict has properties
                        value[
                            "description"
                        ] += f" The dictionary entries have the following schema; they are not in string representation. {json.dumps(value['properties'])}"
                        del value["properties"]

                value["type"] = "string"

    return function


def add_language_specific_hint_to_function_doc(test_cases: list[dict]) -> list[dict]:
    """
    This function adds language-specific hints to the function description and processes the parameters accordingly.
    """
    for entry in test_cases:
        assert "function" in entry
        test_category = extract_test_category_from_id(entry["id"])
        entry["function"] = _func_doc_language_specific_pre_processing(
            entry["function"], test_category
        )

    return test_cases


def process_web_search_test_case(test_cases: list[dict], test_category: str) -> list[dict]:
    """
    Web search test cases need to have their entry id updated. As both the base and no_snippet test categories are using the same question (from the same file), we need to differentiate them here.
    """
    for entry in test_cases:
        entry["id"] = entry["id"].replace("web_search", test_category)

    return test_cases


def process_memory_test_case(
    test_cases: list[dict],
    test_category: str,
    memory_scenario_name: str,
    include_prereq: bool = True,
) -> list[dict]:
    """
    Memory test cases needs to have the memory write phase carried out before the inference phase. So we configure some test case dependencies here.
    Also, we need to configure the proper memory backend for the test cases.
    If `include_prereq` is True, it will include the pre-requisite entries for the memory test categories.
    """
    all_test_cases = []

    pre_req_entries = load_file(
        MEMORY_PREREQ_CONVERSATION_PATH / f"memory_{memory_scenario_name}.json"
    )

    backend_type = extract_memory_backend_type(test_category)
    backend_class_name = f"MemoryAPI_{backend_type}"

    pre_req_ids = []
    # Create and modify pre-requisite entries so that their dependency are properly linked
    for entry in pre_req_entries:
        entry["id"] = entry["id"].replace("memory", test_category)
        entry["depends_on"] = deepcopy(pre_req_ids)
        entry["involved_classes"] = [backend_class_name]
        pre_req_ids.append(entry["id"])
        if include_prereq:
            all_test_cases.append(entry)

    # Update the test case with the backend class name and dependencies
    for entry in test_cases:
        if entry["scenario"] == memory_scenario_name:
            entry["id"] = entry["id"].replace("memory", test_category)
            entry["depends_on"] = deepcopy(pre_req_ids)
            entry["involved_classes"] = [backend_class_name]
        all_test_cases.append(entry)

    return all_test_cases


def process_agentic_test_case(test_cases: list[dict]) -> list[dict]:
    """
    Agentic test cases need to have a specific response format. We add this to the user query here.
    """
    for entry in test_cases:
        if is_agentic(entry["id"]) and not is_memory_prereq(entry["id"]):
            entry["question"][0].insert(
                0,
                {
                    "role": "system",
                    "content": ADDITIONAL_SYSTEM_PROMPT_FOR_AGENTIC_RESPONSE_FORMAT,
                },
            )

    return test_cases


def populate_test_cases_with_predefined_functions(test_cases: list[dict]) -> list[dict]:
    """
    Multi-turn and Agentic test cases don't have the function doc in the prompt. We need to add them here.
    """
    for entry in test_cases:
        if "involved_classes" in entry:
            involved_classes = entry["involved_classes"]
            entry["function"] = []
            for func_collection in involved_classes:
                # func_doc is a list of dict
                func_doc = load_file(
                    MULTI_TURN_FUNC_DOC_PATH / MULTI_TURN_FUNC_DOC_FILE_MAPPING[func_collection]
                )
                entry["function"].extend(func_doc)

        # Handle Miss Func category; we need to remove the holdout function docs
        if "missed_classes" in entry:
            rules = entry["missed_classes"]

            for mc_rule in rules:
                holdout_func_docs = []

                # Remove entire classes of functions
                if "holdout_classes" in mc_rule:
                    for class_name in mc_rule["holdout_classes"]:
                        class_func_docs = load_file(
                            MULTI_TURN_FUNC_DOC_PATH / MULTI_TURN_FUNC_DOC_FILE_MAPPING[class_name]
                        )
                        holdout_func_docs.extend(class_func_docs)
                        holdout_func_names = {f["name"] for f in class_func_docs}
                        entry["function"] = [
                            f for f in entry["function"] if f["name"] not in holdout_func_names
                        ]

                # Remove individual functions
                if "holdout_functions" in mc_rule:
                    for func_name in mc_rule["holdout_functions"]:
                        for i, func_doc in enumerate(entry["function"]):
                            if func_doc["name"] == func_name:
                                holdout_func_docs.append(func_doc)
                                entry["function"].pop(i)
                                break

                mc_rule["holdout_func_docs"] = holdout_func_docs

    return test_cases


def clean_up_memory_prereq_entries(test_cases: list[dict]) -> list[dict]:
    """
    1. Remove memory-prerequisite test cases when their corresponding non-prerequisite memory cases are absent. If all memory questions have been generated, but the pre-requisite entries are not there (maybe deleted), there is no point to generate the pre-requisite entries again.
    2. If, for some reason, some of the pre-req enries have been genrated, then they should be removed from the dependency list. Otherwise, the dependency list will block forever.
    """
    memory_entries = [entry for entry in test_cases if is_memory(entry["id"])]

    # Group test cases by their category to help identify the count
    test_cases_by_category = {}
    for entry in memory_entries:
        test_category = extract_test_category_from_id(entry["id"])
        test_cases_by_category.setdefault(test_category, []).append(entry)

    for test_category, category_test_cases in test_cases_by_category.items():
        if is_memory_prereq(test_category) and len(category_test_cases) != 0:
            if test_category.replace("_prereq", "") not in test_cases_by_category:
                # Remove the memory pre-requisite entries from the test cases
                for entry in category_test_cases:
                    test_cases.remove(entry)

    # Remove already-generated entries from dependency lists to prevent blocking
    test_case_ids_to_generate = {entry["id"] for entry in test_cases}
    for test_case in test_cases:
        if "depends_on" in test_case:
            test_case["depends_on"] = [
                dep_id
                for dep_id in test_case["depends_on"]
                if dep_id in test_case_ids_to_generate
            ]

    return test_cases


def resolve_initial_config_file_paths(
    test_cases: list[dict], base_dir: Path
) -> list[dict]:
    """
    Resolve initial_config values that are file path strings.

    An entry's initial_config maps class names to either an inline config dict
    or a string file path pointing to an external JSON config file.  When the
    value is a string, this function loads the referenced JSON file (resolved
    relative to *base_dir*) and replaces the string with the loaded dict.

    Inline dict (no change):
        "initial_config": {
            "GorillaFileSystem": {"root": {"workspace": {"type": "directory", ...}}}
        }

    File path string (resolved to loaded JSON):
        "initial_config": {
            "WeatherCom": "./weather_com_variants/weather_com_west.json"
        }
        ->
        "initial_config": {
            "WeatherCom": { <contents of weather_com_west.json> }
        }
    """
    
    # @HuanzhiMao FIXME: Revert back after fixing dataset issue
    """
    for entry in test_cases:
        init_config = entry.get("initial_config")
        if not isinstance(init_config, dict):
            continue
        for class_name, config_value in init_config.items():
            if isinstance(config_value, str):
                config_path = (base_dir / config_value).resolve()
                with open(config_path) as f:
                    init_config[class_name] = json.load(f)
    return test_cases

    """
    valid_test_cases = []
    for entry in test_cases:
        init_config = entry.get("initial_config")
        if not isinstance(init_config, dict):
            valid_test_cases.append(entry)
            continue
        try:
            for class_name, config_value in init_config.items():
                if isinstance(config_value, str):
                    config_path = (base_dir / config_value).resolve()
                    with open(config_path) as f:
                        init_config[class_name] = json.load(f)
            valid_test_cases.append(entry)
        except Exception as e:
            logging.warning(
                f"Skipping entry '{entry.get('id', 'unknown')}' "
                f"(source: {entry.get('_source', 'N/A')}): {e}"
            )
    return valid_test_cases


def populate_initial_settings_for_memory_test_cases(
    test_cases: list[dict], model_result_dir: Path
) -> list[dict]:
    """
    Special handling for the memory category, as it loads the initial configuration from local files
    """
    for entry in test_cases:
        if is_memory(entry["id"]):
            involved_classes = entry["involved_classes"]

            init_config = {
                involved_classes[0]: {
                    "model_result_dir": model_result_dir,
                    "scenario": entry["scenario"],
                    "test_id": entry["id"],
                    "test_category": extract_test_category_from_id(entry["id"]),
                }
            }
            entry["initial_config"] = init_config
    return test_cases


def populate_initial_settings_for_web_search_test_cases(
    test_cases: list[dict],
) -> list[dict]:
    """
    Special handling for the web search category, as it controls the show_snippet parameter
    """
    for entry in test_cases:
        if is_web_search(entry["id"]):
            involved_classes = entry["involved_classes"]

            init_config = {
                involved_classes[0]: {
                    "show_snippet": False if "no_snippet" in entry["id"] else True
                }
            }
            entry["initial_config"] = init_config
    return test_cases


#### Utils for Format Sensitivity ####


def load_format_sensitivity_test_cases() -> list[dict]:
    """
    Loads all the format sensitivity test cases. 26 configs x 200 test cases = 5200 test cases.
    """
    _, all_test_entries_involved = load_test_entries_from_id_file(
        FORMAT_SENSITIVITY_IDS_PATH
    )
    all_configs = get_all_format_sensitivity_configs()

    all_format_sensitivity_test_cases = []
    index = 0
    for entry in all_test_entries_involved:
        for config in all_configs:
            entry_copy = deepcopy(entry)
            entry_copy["id"] = f"format_sensitivity_{index}|{config}|{entry_copy['id']}"

            all_format_sensitivity_test_cases.append(entry_copy)
            index += 1

    return all_format_sensitivity_test_cases


def load_format_sensitivity_ground_truth_entry() -> list[dict]:
    all_categories, all_test_entries_involved = load_test_entries_from_id_file(
        FORMAT_SENSITIVITY_IDS_PATH
    )
    all_configs = get_all_format_sensitivity_configs()

    ground_truth_entries = []
    for category in all_categories:
        ground_truth_entries.extend(load_ground_truth_entry(category))

    ground_truth_entries = filter_entries_by_id(
        reference_entries=all_test_entries_involved,
        candidate_entries=ground_truth_entries,
    )

    all_ground_truth_entries = []
    for entry in ground_truth_entries:
        for _ in all_configs:
            all_ground_truth_entries.append(deepcopy(entry))

    return all_ground_truth_entries


def get_all_format_sensitivity_configs() -> list[str]:
    """
    Get all the format sensitivity configs.
    The format sensitivity configs are used to generate the default system prompt for prompting models.
    For a detailed explanation of what each config represents, please refer to our blog post: https://gorilla.cs.berkeley.edu/blogs/17_bfcl_v4_prompt_variation.html#construction
    """

    RETURN_FORMAT = [
        "python",
        "json",
        "verbose_xml",
        "concise_xml",
    ]
    HAS_TOOL_CALL_TAG = ["True", "False"]
    FUNCTION_DOC_FORMAT = [
        "python",
        "xml",
        "json",
    ]

    all_configs = []
    # 4 × 2 × 3 = 24 base combinations
    for return_format in RETURN_FORMAT:
        for has_tool_call_tag in HAS_TOOL_CALL_TAG:
            for function_doc_format in FUNCTION_DOC_FORMAT:
                all_configs.append(
                    f"ret_fmt={return_format}&tool_call_tag={has_tool_call_tag}&func_doc_fmt={function_doc_format}&prompt_fmt=plaintext&style=classic"
                )

    # Add one config with markdown format
    all_configs.append(
        f"ret_fmt=python&tool_call_tag=False&func_doc_fmt=json&prompt_fmt=markdown&style=classic"
    )
    # Add one config with experimental prompt style
    all_configs.append(
        f"ret_fmt=python&tool_call_tag=False&func_doc_fmt=json&prompt_fmt=plaintext&style=experimental"
    )

    return all_configs


#### Utils for Vision ####


_VISION_SUFFIX_MAP = {
    "vision_crop_169": "_169",
    "vision_crop_43": "_43",
    "vision_resize_169": "_resize_169",
    "vision_resize_43": "_resize_43",
    "vision_bw": "_bw",
    "vision_edge": "_edge",
    "vision_rg": "_rg",
}


def process_vision_web_search_test_cases(
    all_entries: list[dict], test_category: str
) -> list[dict]:
    # return [{"id": "vision_base_0", "question": [[{"role": "user", "content": "You must call the fetch_image function to fetch an image and tell me what's in the image."}]], "function": [], "involved_classes": ["StreetViewAPI"]}]
    result = []
    for entry in all_entries:
        user_query = entry["question"][0][0]["content"]
        image_file_name = entry["image_file_name"]
        suffix = _VISION_SUFFIX_MAP.get(test_category, "")
        if suffix:
            image_file_name = image_file_name.replace(".jpeg", f"{suffix}.jpeg")
        image_path = IMAGE_PATH / image_file_name
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        temp = {}
        temp["involved_classes"] = ["VisionSearchAPI"]
        temp["id"] = entry["id"].replace("vision_web_search_base", test_category)
        temp["question"] = [
            [
                {
                    "role": "user",
                    "content": user_query,
                    # @HuanzhiMao FIXME: update all handler for this new format
                    "image_content": [
                        {
                            "image_base64": image_base64,
                            "image_bytes": image_bytes,
                            "image_path": str(image_path),
                            "type": "image/jpeg",
                        }
                    ],
                },
            ]
        ]
        result.append(temp)
    return result


def process_geoguessr_test_case(test_cases: list[dict]) -> list[dict]:
    """
    geoguessr test cases need to have a specific response format. We add this to the user query here.
    """
    for entry in test_cases:
        if is_geoguessr(entry["id"]):
            entry["question"][0].insert(
                0,
                {
                    "role": "system",
                    "content": ADDITIONAL_SYSTEM_PROMPT_FOR_AGENTIC_RESPONSE_FORMAT,
                },
            )

    return test_cases


def query_contains_image_input(message: dict) -> bool:
    """Return True iff the message is a user message that carries raw image."""

    assert type(message) == dict, "Message should be a dict"

    contains_image = "image_content" in message

    # If audio is present, it must come from the user.
    if contains_image and message.get("role") != "user":
        raise ValueError("Image input should only appear in user messages")
    
    return contains_image


#### Audio helper methods ####


def load_audio(path: str) -> bytes:
    """Load audio file from disk given a prefix of the filename.

    The provided *path* is expected to be only a prefix of the actual filename that
    lives inside the ``AUDIO_FILE_PATH`` directory (e.g. ``live_simple_0-0-0_openai``)
    while the real file might be something like
    ``live_simple_0-0-0_openai_audio_mumbling_background_noise_mosquito_db-5_network_cut_n10.mp3``.

    We search for files whose names start with the given prefix and ensure exactly
    one match is found.
    """

    # Ensure we are only dealing with the filename part in case a path is passed in
    prefix = Path(path).name.split(".")[0]  # Strip any possible directories

    # Perform prefix matching recursively inside AUDIO_FILE_PATH and its sub-directories
    candidates = [p for p in AUDIO_FILE_PATH.rglob(f"{prefix}*.*") if p.is_file()]

    if not candidates:
        raise FileNotFoundError(
            f"No audio file found in '{AUDIO_FILE_PATH}' with prefix '{prefix}'."
        )
    if len(candidates) > 1:
        raise RuntimeError(
            "Multiple audio files match the given prefix "
            f"'{prefix}': {[c.name for c in candidates]}"
        )

    audio_path = candidates[0]
    with open(audio_path, "rb") as f:
        return f.read()


def audio_to_base64(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def process_audio_test_case(test_cases: list[dict], modality: Modality) -> list[dict]:
    """
    This function loads the audio query content from the path specified in the test entry.
    """
    for entry in test_cases:
        for turn in entry["question"]:
            for msg in turn:
                if msg["role"] != "user":
                    continue

                assert (
                    "audio_path" in msg
                ), f"Audio path should be specified in the test entry: {entry['id']}"

                if modality == Modality.TRUE_AUDIO:
                    msg["audio_content"] = load_audio(msg["audio_path"])
                    # msg["audio_format"] = "wav"
                    del msg["content"]
                else:
                    assert (
                        modality == Modality.TEXT_AUDIO
                    ), f"Modality {modality} is not a valid modality for audio test cases."
                    # FIXME: uncomment this to determine which text to use
                    # msg["content"] = msg["transcript"]
                    # msg["content"] = msg["asr_output_openai"]
                    # msg["content"] = msg["asr_output_elevenlabs"]
                    msg["original_content"] = msg["content"]
                    msg["content"] = msg["asr_output_deepgram"]

                del msg["transcript"]
                del msg["audio_path"]
                del msg["asr_output_openai"]
                del msg["asr_output_elevenlabs"]
                del msg["asr_output_deepgram"]
        # Merge any existing system prompts with the default audio agent prompt.
        combined_prompts: list[str] = [SYSTEM_PROMPT_FOR_AUDIO_AGENT]

        # Collect contents of all existing system messages across all turns and remove them.
        for turn in entry["question"]:
            for idx in reversed(range(len(turn))):
                if turn[idx].get("role") == "system":
                    content = turn[idx].get("content", "")
                    if (
                        content not in combined_prompts
                    ):  # avoid duplicate if same as default
                        combined_prompts.append(content)
                    del turn[idx]

        merged_system_prompt = "\n\n".join(combined_prompts)

        # Insert the merged system prompt at the very beginning of the conversation.
        entry["question"][0].insert(
            0,
            {
                "role": "system",
                "content": merged_system_prompt,
            },
        )

    return test_cases


def query_contains_audio_input(message: dict) -> bool:
    """Return True iff the message is a user message that carries raw audio."""

    assert type(message) == dict, "Message should be a dict"

    contains_audio = "audio_content" in message

    # If audio is present, it must come from the user.
    if contains_audio and message.get("role") != "user":
        raise ValueError("Audio input should only appear in user messages")

    if contains_audio and len(message.get("content", "")) > 0:
        raise ValueError("Audio input should not have text content at the same time")

    return contains_audio


# @HuanzhiMao FIXME: use data class to abstract the audio message and image message for clearer readability