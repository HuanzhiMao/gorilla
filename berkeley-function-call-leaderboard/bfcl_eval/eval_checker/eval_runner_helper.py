import os
import statistics
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from bfcl_eval.constants.column_headers import *
from bfcl_eval.constants.eval_config import *
from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING
from bfcl_eval.utils import *


def calculate_weighted_accuracy(accuracy_dict_list, display_na_if_category_missing=True):
    has_na = False
    total_count = 0
    total_accuracy = 0
    for accuracy_dict in accuracy_dict_list:
        accuracy = accuracy_dict["accuracy"]
        count = accuracy_dict["total_count"]
        if accuracy_dict["display_accuracy"] == "N/A":
            has_na = True

        total_count += count
        total_accuracy += accuracy * count

    result = {"accuracy": total_accuracy / total_count, "total_count": total_count}

    if has_na and display_na_if_category_missing:
        result["display_accuracy"] = "N/A"
    else:
        result["display_accuracy"] = result["accuracy"]

    return result


def calculate_unweighted_accuracy(accuracy_dict_list, display_na_if_category_missing=True):
    has_na = False
    total_count = 0
    total_accuracy = 0
    for accuracy_dict in accuracy_dict_list:
        accuracy = accuracy_dict["accuracy"]
        count = accuracy_dict["total_count"]
        if accuracy_dict["display_accuracy"] == "N/A":
            # If a category is not being evaluated, it will still be considered 0 in the overall score calculation.
            has_na = True

        total_count += count
        total_accuracy += accuracy

    result = {
        "accuracy": total_accuracy / len(accuracy_dict_list),
        "total_count": total_count,
    }

    if has_na and display_na_if_category_missing:
        result["display_accuracy"] = "N/A"
    else:
        result["display_accuracy"] = result["accuracy"]

    return result


def calculate_percentage_weighted_accuracy(
    accuracy_dict_list, weights, display_na_if_category_missing=True
):
    """
    Calculate accuracy using a fixed list of weights that sum to 1.0.

    Parameters
    ----------
    accuracy_dict_list : list[dict]
        Each element is a dict containing at least the keys ``accuracy``, ``total_count`` and ``display_accuracy``.
    weights : list[float]
        The weight for each corresponding accuracy entry. Can sum to any positive value – they will be normalised internally.
    display_na_if_category_missing : bool, default True
        If True and any of the input categories has ``display_accuracy`` equal to "N/A", the returned ``display_accuracy`` will also be "N/A".

    Returns
    -------
    dict
        A dict with the same schema as other helper functions in this module (``accuracy``, ``total_count``, ``display_accuracy``).
    """
    assert len(accuracy_dict_list) == len(
        weights
    ), "Weights length must match accuracy list"

    has_na = False
    total_count = 0
    total_accuracy = 0.0
    weight_sum = sum(weights)
    if weight_sum == 0:
        raise ValueError("Sum of weights must be greater than 0")

    # Normalise weights so that they sum to 1.0
    weights_norm = [w / weight_sum for w in weights]

    for accuracy_dict, weight in zip(accuracy_dict_list, weights_norm):
        accuracy = accuracy_dict["accuracy"]
        count = accuracy_dict["total_count"]
        if accuracy_dict["display_accuracy"] == "N/A":
            has_na = True

        total_count += count
        total_accuracy += accuracy * weight

    result = {"accuracy": total_accuracy, "total_count": total_count}

    if has_na and display_na_if_category_missing:
        result["display_accuracy"] = "N/A"
    else:
        result["display_accuracy"] = result["accuracy"]

    return result


def record_result(leaderboard_table, model_name, test_category, accuracy, total_count):
    modality = get_category_modality(test_category).value
    base_category = get_base_category(test_category)
    if model_name not in leaderboard_table:
        leaderboard_table[model_name] = {}
    if modality not in leaderboard_table[model_name]:
        leaderboard_table[model_name][modality] = {}
    leaderboard_table[model_name][modality][base_category] = {
        "accuracy": accuracy,
        "total_count": total_count,
    }


def record_cost_latency(leaderboard_table, model_name, test_category, model_output_data):
    modality = get_category_modality(test_category).value

    def process_data(key, data, output_list):
        # All entries are either a list of list (in multi-turn), or a single value (in single-turn)
        if key in data:
            if isinstance(data[key], list) and all(
                isinstance(inner_item, list) for inner_item in data[key]
            ):
                flattened_list = sum(data[key], [])
                output_list.extend(
                    [
                        item
                        for item in flattened_list
                        if isinstance(item, (int, float)) and item != 0
                    ]
                )
            else:
                if isinstance(data[key], (int, float)) and data[key] != 0:
                    output_list.append(data[key])

    if model_name not in leaderboard_table:
        leaderboard_table[model_name] = {}
    if modality not in leaderboard_table[model_name]:
        leaderboard_table[model_name][modality] = {}
    if "cost" not in leaderboard_table[model_name][modality]:
        leaderboard_table[model_name][modality]["cost"] = {"input_data": [], "output_data": []}
    if "latency" not in leaderboard_table[model_name][modality]:
        leaderboard_table[model_name][modality]["latency"] = {"data": []}

    input_token = []
    output_token = []
    latency = []
    for data in model_output_data:
        process_data("latency", data, latency)
        process_data("input_token_count", data, input_token)
        process_data("output_token_count", data, output_token)

    leaderboard_table[model_name][modality]["cost"]["input_data"].extend(input_token)
    leaderboard_table[model_name][modality]["cost"]["output_data"].extend(output_token)
    leaderboard_table[model_name][modality]["latency"]["data"].extend(latency)


def save_eval_results(
    result,
    correct_count,
    model_result,
    test_category,
    model_name,
    score_dir,
    extra_header_fields: dict = None,
) -> tuple[float, int]:
    """
    Compute accuracy, finalize evaluation results and write them to disk.
    Return the accuracy and the total number of test cases.
    """
    accuracy = correct_count / len(model_result)
    header = {
        "accuracy": accuracy,
        "correct_count": correct_count,
        "total_count": len(model_result),
    }
    if extra_header_fields:
        header.update(extra_header_fields)

    result.insert(0, header)
    base_category = get_base_category(test_category)
    output_file_name = f"{base_category}_score.json"
    output_file_dir = (
        score_dir / model_name / get_directory_structure_by_category(test_category)
    )
    write_list_of_dicts_to_file(output_file_name, result, output_file_dir)

    return accuracy, len(model_result)


def get_cost_latency_info(model_name, cost_data, latency_data):
    cost, mean_latency, std_latency, percentile_95_latency = "N/A", "N/A", "N/A", "N/A"
    model_config = MODEL_CONFIG_MAPPING[model_name]

    # For API models, we use the input and output token counts to calculate the cost
    if model_config.input_price is not None and model_config.output_price is not None:
        if len(cost_data["input_data"]) > 0 and len(cost_data["output_data"]) > 0:
            total_input_tokens = sum(cost_data["input_data"])
            total_output_tokens = sum(cost_data["output_data"])
            # price is in USD per million tokens
            cost = (
                total_input_tokens * model_config.input_price / 1000000
                + total_output_tokens * model_config.output_price / 1000000
            )
            cost = round(cost, 2)

    # For local-hosted models, we calculate the total GPU cost by summing all latencies and multiplying by the hourly GPU price.
    elif len(latency_data["data"]) > 0:
        total_latency_seconds = sum(latency_data["data"])
        total_latency_hours = total_latency_seconds / 3600

        # Divide by 100 since we are doing 100x parallel inference; this is an approximation to the GPU up-time.
        cost = (
            total_latency_hours
            * H100_X8_PRICE_PER_HOUR
            / LOCAL_SERVER_MAX_CONCURRENT_REQUEST
        )
        cost = round(cost, 2)

    # Calculate latency statistics for ALL models (both API and local)
    if len(latency_data["data"]) != 0:
        mean_latency = statistics.mean(latency_data["data"])
        std_latency = statistics.stdev(latency_data["data"])
        percentile_95_latency = np.percentile(latency_data["data"], 95)
        mean_latency = round(mean_latency, 2)
        std_latency = round(std_latency, 2)
        percentile_95_latency = round(percentile_95_latency, 2)

    return cost, mean_latency, std_latency, percentile_95_latency


def get_category_score(modality_dict: dict, base_category: str, modality: str) -> dict:
    """Look up a category score from a per-modality sub-dict.

    Parameters
    ----------
    modality_dict : dict
        ``leaderboard_table[model_name][modality]`` – the sub-dict for one modality.
    base_category : str
        The base category name without modality prefix (e.g. ``"simple_python"``).
    modality : str
        The modality value string (e.g. ``"text"``), used to construct the full
        prefixed category when falling back to ``load_dataset_entry``.
    """
    if base_category in modality_dict:
        score = modality_dict[base_category]
        score["display_accuracy"] = score["accuracy"]
        return score
    else:
        full_category = f"{modality}:{base_category}"
        num_entry = len(
            load_dataset_entry(
                full_category, include_prereq=False, include_language_specific_hint=False
            )
        )
        # If a category is not being evaluated, it needs to be distinguished from the situation where the evaluation score is 0
        # It will still be considered 0 in the overall score calculation though
        # We use `display_accuracy` to special handle
        return {"accuracy": 0, "total_count": num_entry, "display_accuracy": "N/A"}


def write_score_csv_file(
    data,
    file_path: str,
    header: list,
    sort_column_index: int,
    no_conversion_numeric_column_index: list[int] = [],
) -> None:
    # Sort the data by the target column. Any row that contains "N/A" in the sort
    # column should always be placed at the end of the list. We achieve this by
    # returning -1 for such rows (all valid accuracy values are in the range [0, 1]),
    # and then performing a regular descending sort.
    data.sort(
        key=lambda x: x[sort_column_index] if x[sort_column_index] != "N/A" else -1,
        reverse=True,
    )
    for i in range(len(data)):
        # Add the ranking column, start from 0
        data[i][0] = str(i + 1)
        for j in range(1, len(data[i])):
            if type(data[i][j]) == str:
                continue
            # Some columns such as Latency and Cost, should not be presented in the percentage format
            elif j in no_conversion_numeric_column_index:
                data[i][j] = str(data[i][j])
            else:
                # Convert numeric value to percentage format
                data[i][j] = "{:.2f}%".format(data[i][j] * 100)

    data.insert(0, header)

    with open(file_path, "w") as f:
        for i, row in enumerate(data):
            if i < len(data) - 1:
                f.write(",".join(row) + "\n")
            else:
                f.write(",".join(row))


def _aggregate_cost_latency_across_modalities(value):
    """Aggregate cost and latency data across all modalities for a single model.

    ``value`` is ``leaderboard_table[model_name]`` whose keys are modality
    names, each containing optional ``"cost"`` and ``"latency"`` sub-dicts.
    """
    cost_all = {"input_data": [], "output_data": []}
    latency_all = {"data": []}
    for modality_data in value.values():
        if not isinstance(modality_data, dict):
            continue
        modality_cost = modality_data.get("cost", {})
        cost_all["input_data"].extend(modality_cost.get("input_data", []))
        cost_all["output_data"].extend(modality_cost.get("output_data", []))
        modality_latency = modality_data.get("latency", {})
        latency_all["data"].extend(modality_latency.get("data", []))
    return cost_all, latency_all


def _compute_non_live_scores(modality_dict, modality):
    """Compute non-live category scores for a given modality sub-dict."""
    python_simple = get_category_score(modality_dict, "simple_python", modality)
    python_multiple = get_category_score(modality_dict, "multiple", modality)
    python_parallel = get_category_score(modality_dict, "parallel", modality)
    python_parallel_multiple = get_category_score(modality_dict, "parallel_multiple", modality)
    java_simple = get_category_score(modality_dict, "simple_java", modality)
    js_simple = get_category_score(modality_dict, "simple_javascript", modality)
    irrelevance = get_category_score(modality_dict, "irrelevance", modality)

    simple_ast = calculate_unweighted_accuracy([python_simple, java_simple, js_simple])
    summary_ast = calculate_unweighted_accuracy(
        [simple_ast, python_multiple, python_parallel, python_parallel_multiple]
    )
    overall = calculate_unweighted_accuracy(
        [simple_ast, python_multiple, python_parallel, python_parallel_multiple],
        display_na_if_category_missing=False,
    )
    return {
        "python_simple": python_simple,
        "python_multiple": python_multiple,
        "python_parallel": python_parallel,
        "python_parallel_multiple": python_parallel_multiple,
        "java_simple": java_simple,
        "js_simple": js_simple,
        "irrelevance": irrelevance,
        "simple_ast": simple_ast,
        "summary_ast": summary_ast,
        "overall": overall,
    }


def _compute_live_scores(modality_dict, modality):
    """Compute live category scores for a given modality sub-dict."""
    simple = get_category_score(modality_dict, "live_simple", modality)
    multiple = get_category_score(modality_dict, "live_multiple", modality)
    parallel = get_category_score(modality_dict, "live_parallel", modality)
    parallel_multiple = get_category_score(modality_dict, "live_parallel_multiple", modality)
    irrelevance = get_category_score(modality_dict, "live_irrelevance", modality)
    relevance = get_category_score(modality_dict, "live_relevance", modality)

    summary_ast = calculate_weighted_accuracy(
        [simple, multiple, parallel, parallel_multiple]
    )
    overall = calculate_weighted_accuracy(
        [simple, multiple, parallel, parallel_multiple],
        display_na_if_category_missing=False,
    )
    return {
        "simple": simple,
        "multiple": multiple,
        "parallel": parallel,
        "parallel_multiple": parallel_multiple,
        "irrelevance": irrelevance,
        "relevance": relevance,
        "summary_ast": summary_ast,
        "overall": overall,
    }


def _compute_multi_turn_scores(modality_dict, modality):
    """Compute multi-turn category scores for a given modality sub-dict."""
    base = get_category_score(modality_dict, "multi_turn_base", modality)
    miss_func = get_category_score(modality_dict, "multi_turn_miss_func", modality)
    miss_param = get_category_score(modality_dict, "multi_turn_miss_param", modality)
    long_context = get_category_score(modality_dict, "multi_turn_long_context", modality)
    overall = calculate_unweighted_accuracy(
        [base, miss_func, miss_param, long_context],
        display_na_if_category_missing=False,
    )
    return {
        "base": base,
        "miss_func": miss_func,
        "miss_param": miss_param,
        "long_context": long_context,
        "overall": overall,
    }


def _build_non_live_row(display_name, nl):
    """Build a CSV row for the non-live sub-table."""
    return [
        "N/A",
        display_name,
        nl["overall"]["display_accuracy"],
        nl["summary_ast"]["display_accuracy"],
        nl["simple_ast"]["display_accuracy"],
        nl["python_simple"]["display_accuracy"],
        nl["java_simple"]["display_accuracy"],
        nl["js_simple"]["display_accuracy"],
        nl["python_multiple"]["display_accuracy"],
        nl["python_parallel"]["display_accuracy"],
        nl["python_parallel_multiple"]["display_accuracy"],
        nl["irrelevance"]["display_accuracy"],
    ]


def _build_live_row(display_name, lv):
    """Build a CSV row for the live sub-table."""
    return [
        "N/A",
        display_name,
        lv["overall"]["display_accuracy"],
        lv["summary_ast"]["display_accuracy"],
        lv["simple"]["display_accuracy"],
        lv["multiple"]["display_accuracy"],
        lv["parallel"]["display_accuracy"],
        lv["parallel_multiple"]["display_accuracy"],
        lv["irrelevance"]["display_accuracy"],
        lv["relevance"]["display_accuracy"],
    ]


def _build_multi_turn_row(display_name, mt):
    """Build a CSV row for the multi-turn sub-table."""
    return [
        "N/A",
        display_name,
        mt["overall"]["display_accuracy"],
        mt["base"]["display_accuracy"],
        mt["miss_func"]["display_accuracy"],
        mt["miss_param"]["display_accuracy"],
        mt["long_context"]["display_accuracy"],
    ]


def _build_audio_overall_row(display_name, nl, lv, mt, total_irrelevance, modality_overall):
    """Build a CSV row for an audio modality overall table."""
    return [
        "N/A",
        modality_overall["display_accuracy"],
        display_name,
        nl["summary_ast"]["display_accuracy"],
        nl["simple_ast"]["display_accuracy"],
        nl["python_multiple"]["display_accuracy"],
        nl["python_parallel"]["display_accuracy"],
        nl["python_parallel_multiple"]["display_accuracy"],
        lv["overall"]["display_accuracy"],
        lv["simple"]["display_accuracy"],
        lv["multiple"]["display_accuracy"],
        lv["parallel"]["display_accuracy"],
        lv["parallel_multiple"]["display_accuracy"],
        mt["overall"]["display_accuracy"],
        mt["base"]["display_accuracy"],
        mt["miss_func"]["display_accuracy"],
        mt["miss_param"]["display_accuracy"],
        mt["long_context"]["display_accuracy"],
        lv["relevance"]["display_accuracy"],
        total_irrelevance["display_accuracy"],
    ]


def generate_leaderboard_csv(leaderboard_table, output_path):
    print("📈 Aggregating data to generate leaderboard score table...")
    all_format_configs = get_all_format_sensitivity_configs()

    # Text modality data
    data_text_non_live = []
    data_text_live = []
    data_text_multi_turn = []
    data_text_agentic = []
    data_text_format_sensitivity = []
    data_text_overall = []

    # Audio modality data (true_audio and text_audio)
    data_true_audio_non_live = []
    data_true_audio_live = []
    data_true_audio_multi_turn = []
    data_true_audio_overall = []
    data_text_audio_non_live = []
    data_text_audio_live = []
    data_text_audio_multi_turn = []
    data_text_audio_overall = []

    # Vision modality data
    data_vision_overall = []

    # Cross-modality overall
    data_combined = []

    for model_name, value in leaderboard_table.items():
        model_name_escaped = model_name.replace("_", "/")
        model_config = MODEL_CONFIG_MAPPING[model_name_escaped]

        # Aggregate cost/latency across all modalities
        cost_data_all, latency_data_all = _aggregate_cost_latency_across_modalities(value)
        cost, latency_mean, latency_std, percentile_95_latency = get_cost_latency_info(
            model_name_escaped, cost_data_all, latency_data_all
        )

        # ---- Text Modality ---- #
        text_data = value.get("text", {})
        text_nl = _compute_non_live_scores(text_data, "text")
        text_lv = _compute_live_scores(text_data, "text")
        text_mt = _compute_multi_turn_scores(text_data, "text")

        data_text_non_live.append(_build_non_live_row(model_config.display_name, text_nl))
        data_text_live.append(_build_live_row(model_config.display_name, text_lv))
        data_text_multi_turn.append(_build_multi_turn_row(model_config.display_name, text_mt))

        # Agentic (text only)
        text_ws_base = get_category_score(text_data, "web_search_base", "text")
        text_ws_no_snippet = get_category_score(text_data, "web_search_no_snippet", "text")
        text_summary_ws = calculate_unweighted_accuracy([text_ws_base, text_ws_no_snippet])
        text_mem_kv = get_category_score(text_data, "memory_kv", "text")
        text_mem_vector = get_category_score(text_data, "memory_vector", "text")
        text_mem_rec_sum = get_category_score(text_data, "memory_rec_sum", "text")
        text_summary_mem = calculate_unweighted_accuracy(
            [text_mem_kv, text_mem_vector, text_mem_rec_sum]
        )
        text_overall_agentic = calculate_unweighted_accuracy(
            [text_summary_ws, text_summary_mem],
            display_na_if_category_missing=False,
        )

        data_text_agentic.append(
            [
                "N/A",
                model_config.display_name,
                text_overall_agentic["display_accuracy"],
                text_summary_ws["display_accuracy"],
                text_ws_base["display_accuracy"],
                text_ws_no_snippet["display_accuracy"],
                text_summary_mem["display_accuracy"],
                text_mem_kv["display_accuracy"],
                text_mem_vector["display_accuracy"],
                text_mem_rec_sum["display_accuracy"],
            ]
        )

        # Format Sensitivity (text only)
        format_sensitivity_metadata = text_data.get("format_sensitivity", {})
        format_sensitivity_max_delta = format_sensitivity_metadata.get(
            "accuracy_max_delta", "N/A"
        )
        format_sensitivity_std = format_sensitivity_metadata.get("accuracy_std", "N/A")

        config_accuracy_values = []
        for cfg in all_format_configs:
            cfg_stats = format_sensitivity_metadata.get(cfg, {})
            cfg_acc = cfg_stats.get("accuracy", "N/A")
            config_accuracy_values.append(cfg_acc)

        data_text_format_sensitivity.append(
            [
                "N/A",
                model_config.display_name,
                format_sensitivity_max_delta,
                format_sensitivity_std,
                *config_accuracy_values,
            ]
        )

        # Text Overall
        text_total_irrelevance = calculate_unweighted_accuracy(
            [text_nl["irrelevance"], text_lv["irrelevance"]]
        )

        # TODO: @HuanzhiMao adjust the weights
        text_total_overall = calculate_percentage_weighted_accuracy(
            [
                text_nl["overall"],
                text_lv["overall"],
                text_total_irrelevance,
                text_mt["overall"],
                text_overall_agentic,
            ],
            [10, 10, 10, 30, 40],
            display_na_if_category_missing=False,
        )

        data_text_overall.append(
            [
                "N/A",
                text_total_overall["display_accuracy"],
                model_config.display_name,
                text_nl["summary_ast"]["display_accuracy"],
                text_nl["simple_ast"]["display_accuracy"],
                text_nl["python_multiple"]["display_accuracy"],
                text_nl["python_parallel"]["display_accuracy"],
                text_nl["python_parallel_multiple"]["display_accuracy"],
                text_lv["overall"]["display_accuracy"],
                text_lv["simple"]["display_accuracy"],
                text_lv["multiple"]["display_accuracy"],
                text_lv["parallel"]["display_accuracy"],
                text_lv["parallel_multiple"]["display_accuracy"],
                text_mt["overall"]["display_accuracy"],
                text_mt["base"]["display_accuracy"],
                text_mt["miss_func"]["display_accuracy"],
                text_mt["miss_param"]["display_accuracy"],
                text_mt["long_context"]["display_accuracy"],
                text_summary_ws["display_accuracy"],
                text_ws_base["display_accuracy"],
                text_ws_no_snippet["display_accuracy"],
                text_summary_mem["display_accuracy"],
                text_mem_kv["display_accuracy"],
                text_mem_vector["display_accuracy"],
                text_mem_rec_sum["display_accuracy"],
                text_lv["relevance"]["display_accuracy"],
                text_total_irrelevance["display_accuracy"],
                format_sensitivity_max_delta,
                format_sensitivity_std,
            ]
        )

        # ---- Audio Modalities (true_audio and text_audio) ---- #
        audio_modality_overalls = {}
        for audio_prefix, data_nl, data_l, data_mt_list, data_ov in [
            ("true_audio", data_true_audio_non_live, data_true_audio_live, data_true_audio_multi_turn, data_true_audio_overall),
            ("text_audio", data_text_audio_non_live, data_text_audio_live, data_text_audio_multi_turn, data_text_audio_overall),
        ]:
            audio_data = value.get(audio_prefix, {})
            a_nl = _compute_non_live_scores(audio_data, audio_prefix)
            a_lv = _compute_live_scores(audio_data, audio_prefix)
            a_mt = _compute_multi_turn_scores(audio_data, audio_prefix)

            data_nl.append(_build_non_live_row(model_config.display_name, a_nl))
            data_l.append(_build_live_row(model_config.display_name, a_lv))
            data_mt_list.append(_build_multi_turn_row(model_config.display_name, a_mt))

            # Audio Overall (unweighted average of non-live, live, irrelevance, multi-turn)
            a_total_irrelevance = calculate_unweighted_accuracy(
                [a_nl["irrelevance"], a_lv["irrelevance"]]
            )
            a_modality_overall = calculate_unweighted_accuracy(
                [a_nl["overall"], a_lv["overall"], a_total_irrelevance, a_mt["overall"]],
                display_na_if_category_missing=False,
            )
            audio_modality_overalls[audio_prefix] = a_modality_overall

            data_ov.append(
                _build_audio_overall_row(
                    model_config.display_name, a_nl, a_lv, a_mt,
                    a_total_irrelevance, a_modality_overall,
                )
            )

        # ---- Vision Modality ---- #
        vision_data = value.get("vision", {})
        vision_geo_t1 = get_category_score(vision_data, "geoguessr_type1", "vision")
        vision_geo_t2 = get_category_score(vision_data, "geoguessr_type2", "vision")
        vision_geo_t3 = get_category_score(vision_data, "geoguessr_type3", "vision")
        vision_overall = calculate_unweighted_accuracy(
            [vision_geo_t1, vision_geo_t2, vision_geo_t3],
            display_na_if_category_missing=False,
        )

        data_vision_overall.append(
            [
                "N/A",
                model_config.display_name,
                vision_overall["display_accuracy"],
                vision_geo_t1["display_accuracy"],
                vision_geo_t2["display_accuracy"],
                vision_geo_t3["display_accuracy"],
            ]
        )

        # ---- Cross-Modality Overall ---- #
        cross_modality_overall = calculate_unweighted_accuracy(
            [
                text_total_overall,
                audio_modality_overalls["true_audio"],
                audio_modality_overalls["text_audio"],
                vision_overall,
            ],
            display_na_if_category_missing=False,
        )

        data_combined.append(
            [
                "N/A",
                cross_modality_overall["display_accuracy"],
                model_config.display_name,
                model_config.url,
                cost,
                latency_mean,
                latency_std,
                percentile_95_latency,
                text_total_overall["display_accuracy"],
                audio_modality_overalls["true_audio"]["display_accuracy"],
                audio_modality_overalls["text_audio"]["display_accuracy"],
                vision_overall["display_accuracy"],
                model_config.org,
                model_config.license,
            ]
        )

    # ---- Write Text CSV Files ---- #
    write_score_csv_file(
        data=data_text_non_live,
        file_path=output_path / "score_text_non_live.csv",
        header=COLUMNS_TEXT_NON_LIVE,
        sort_column_index=2,
    )
    write_score_csv_file(
        data=data_text_live,
        file_path=output_path / "score_text_live.csv",
        header=COLUMNS_TEXT_LIVE,
        sort_column_index=2,
    )
    write_score_csv_file(
        data=data_text_multi_turn,
        file_path=output_path / "score_text_multi_turn.csv",
        header=COLUMNS_TEXT_MULTI_TURN,
        sort_column_index=2,
    )
    write_score_csv_file(
        data=data_text_agentic,
        file_path=output_path / "score_text_agentic.csv",
        header=COLUMNS_TEXT_AGENTIC,
        sort_column_index=2,
    )

    COLUMNS_FORMAT_SENS = COLUMNS_TEXT_FORMAT_SENS_PREFIX + [
        f"Config {cfg}" for cfg in all_format_configs
    ]
    write_score_csv_file(
        data=data_text_format_sensitivity,
        file_path=output_path / "score_text_format_sensitivity.csv",
        header=COLUMNS_FORMAT_SENS,
        sort_column_index=2,
        no_conversion_numeric_column_index=[2, 3],
    )

    write_score_csv_file(
        data=data_text_overall,
        file_path=output_path / "score_text_overall.csv",
        header=COLUMNS_TEXT_OVERALL,
        sort_column_index=1,
        no_conversion_numeric_column_index=[27, 28],
    )

    # ---- Write Audio CSV Files ---- #
    for audio_prefix, data_nl, data_l, data_mt_list, data_ov in [
        ("true_audio", data_true_audio_non_live, data_true_audio_live, data_true_audio_multi_turn, data_true_audio_overall),
        ("text_audio", data_text_audio_non_live, data_text_audio_live, data_text_audio_multi_turn, data_text_audio_overall),
    ]:
        write_score_csv_file(
            data=data_nl,
            file_path=output_path / f"score_{audio_prefix}_non_live.csv",
            header=COLUMNS_AUDIO_NON_LIVE,
            sort_column_index=2,
        )
        write_score_csv_file(
            data=data_l,
            file_path=output_path / f"score_{audio_prefix}_live.csv",
            header=COLUMNS_AUDIO_LIVE,
            sort_column_index=2,
        )
        write_score_csv_file(
            data=data_mt_list,
            file_path=output_path / f"score_{audio_prefix}_multi_turn.csv",
            header=COLUMNS_AUDIO_MULTI_TURN,
            sort_column_index=2,
        )
        write_score_csv_file(
            data=data_ov,
            file_path=output_path / f"score_{audio_prefix}_overall.csv",
            header=COLUMNS_AUDIO_OVERALL,
            sort_column_index=1,
        )

    # ---- Write Vision CSV Files ---- #
    write_score_csv_file(
        data=data_vision_overall,
        file_path=output_path / "score_vision_overall.csv",
        header=COLUMNS_VISION_OVERALL,
        sort_column_index=2,
    )

    # ---- Write Cross-Modality Overall CSV ---- #
    write_score_csv_file(
        data=data_combined,
        file_path=output_path / "score_overall.csv",
        header=COLUMNS_OVERALL,
        sort_column_index=1,
        no_conversion_numeric_column_index=[4, 5, 6, 7],
    )

    # ---- WandB Logging ---- #
    wandb_project = os.getenv("WANDB_BFCL_PROJECT")
    if wandb_project and wandb_project != "ENTITY:PROJECT":
        import wandb

        wandb.init(
            entity=wandb_project.split(":")[0],
            project=wandb_project.split(":")[1],
            name=f"BFCL-v4-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        )

        csv_files = {
            "Text Non-Live": "score_text_non_live.csv",
            "Text Live": "score_text_live.csv",
            "Text Multi-Turn": "score_text_multi_turn.csv",
            "Text Agentic": "score_text_agentic.csv",
            "Text Overall": "score_text_overall.csv",
            "True Audio Overall": "score_true_audio_overall.csv",
            "Text Audio Overall": "score_text_audio_overall.csv",
            "Vision Overall": "score_vision_overall.csv",
            "Overall": "score_overall.csv",
        }

        bfcl_artifact = wandb.Artifact("bfcl_results", type="dataset")
        tables = {}
        for label, filename in csv_files.items():
            df = pd.read_csv(output_path / filename)
            table = wandb.Table(dataframe=df)
            tables[label] = table
            artifact_name = filename.replace(".csv", "").replace("score_", "") + "_results"
            bfcl_artifact.add(table, artifact_name)
            bfcl_artifact.add_file(str(output_path / filename))

        wandb.log(tables)
        wandb.log_artifact(bfcl_artifact)
        wandb.finish()


def update_leaderboard_table_with_local_score_file(
    leaderboard_table, score_path: Path
) -> None:

    entries = score_path.iterdir()

    # Filter out the subdirectories
    subdirs = [entry for entry in entries if entry.is_dir()]

    # Traverse each subdirectory
    for subdir in subdirs:
        model_name = subdir.relative_to(score_path).name
        # Find and process all score JSON files recursively in the subdirectory
        for model_score_json in subdir.rglob(SCORE_FILE_PATTERN):
            metadata = load_file(model_score_json)[0]
            base_category = extract_test_category(model_score_json)
            modality = detect_modality_from_path(model_score_json, subdir)
            if model_name not in leaderboard_table:
                leaderboard_table[model_name] = {}
            if modality not in leaderboard_table[model_name]:
                leaderboard_table[model_name][modality] = {}
            # Store the full metadata to retain additional statistics (e.g. format sensitivity breakdown)
            leaderboard_table[model_name][modality][base_category] = metadata
