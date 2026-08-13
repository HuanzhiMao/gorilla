import argparse
import statistics
from collections import defaultdict

from bfcl_eval.constants.enums import Language, ReturnFormat
from bfcl_eval.constants.eval_config import *
from bfcl_eval.constants.model_config import (
    DIR_NAME_TO_REGISTRY,
    MODEL_CONFIG_MAPPING,
    REGISTRY_TO_DIR_NAME,
)
from bfcl_eval.eval_checker.agentic_eval.agentic_checker import agentic_checker
from bfcl_eval.eval_checker.ast_eval.ast_checker import ast_checker
from bfcl_eval.eval_checker.eval_runner_helper import *
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import (
    multi_turn_checker,
    multi_turn_func_call_constraint_checker,
    multi_turn_irrelevance_checker,
)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import (
    is_empty_execute_response,
)
from bfcl_eval.eval_checker.vision_eval.vision_checker import vision_checker
from bfcl_eval.dataset_loader import load_dataset_entries, load_ground_truth_entries
from bfcl_eval.model_handler.base_handler import BaseHandler
from bfcl_eval.schemas.category import AST_STRATEGIES, EvalStrategy, TestCategory
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.ground_truth import GroundTruth, GroundTruthKind
from bfcl_eval.utils import *
from dotenv import load_dotenv
from tqdm import tqdm


def get_handler(model_name: str) -> BaseHandler:
    config = MODEL_CONFIG_MAPPING[model_name]
    handler: BaseHandler = config.model_handler(
        model_name=config.model_name,
        temperature=0,
        registry_name=model_name,
    )
    return handler


def _prompt_for_score(entry: TestEntry) -> dict:
    """Render an entry for a score file: everything except the tool definitions.

    The function docs are dropped purely for readability -- they are large, identical
    across every entry of a category, and not useful when reading a failure.
    """
    rendered = entry.to_dict()
    rendered.pop("function", None)
    return rendered


def _subset_entries_by_model_ids(
    model_result_entries: list[dict],
    prompt_entries: list[TestEntry],
    ground_truth_entries: list[GroundTruth] = None,  # Relevance entries have no ground truth
    allow_missing: bool = False,
):
    """
    Filter the prompt and ground truth entries so that its order/length matches the IDs present in `model_result`. When `allow_missing` is False, all IDs must be present; otherwise, any missing IDs are silently ignored.
    """
    if not model_result_entries:
        return [], []

    if not allow_missing and (len(model_result_entries) != len(prompt_entries)):
        raise ValueError(
            f"Length of model result ({len(model_result_entries)}) does not match length of test entries ({len(prompt_entries)}). If you intended to run only on a subset (eg. entries present in the model result), please pass the `--partial-eval` flag."
        )

    all_present_ids = {entry["id"]: entry for entry in model_result_entries}

    # Pair each prompt with its ground truth by *id*. This used to be done by list
    # index, because ground-truth ids were prefixed with the Modality enum's repr and
    # so never matched a prompt id; now that they agree, pairing by id means a
    # reordered or partially-regenerated ground-truth file can no longer silently
    # score entries against the wrong expectation.
    ground_truth_by_id = (
        {entry.id: entry for entry in ground_truth_entries}
        if ground_truth_entries is not None
        else None
    )

    filtered_prompt_entries: list[TestEntry] = []
    filtered_ground_truth_entries: list[GroundTruth] = []
    for prompt_entry in prompt_entries:
        if prompt_entry.id not in all_present_ids:
            continue
        filtered_prompt_entries.append(prompt_entry)
        if ground_truth_by_id is not None:
            try:
                filtered_ground_truth_entries.append(ground_truth_by_id[prompt_entry.id])
            except KeyError:
                raise ValueError(
                    f"No ground truth for {prompt_entry.id}. The prompt and "
                    f"ground-truth files for this category are out of sync."
                ) from None

    return filtered_prompt_entries, filtered_ground_truth_entries


def _evaluate_single_vision_geoguessr_entry(
    handler: BaseHandler,
    index,
    model_result_list,
    ground_truth: GroundTruth,
    entry: TestEntry,
    model_name,
    test_category,
):
    """Helper method to process a single vision geoguessr entry."""
    prompt_entry = _prompt_for_score(entry)
    possible_answer_item = ground_truth.payload

    # Vision geoguessr test is a single-turn test, so the model result should be a list of one element
    if type(model_result_list) != list or len(model_result_list) != 1:
        return {
            "id": index,
            "score": 0.0,
            "model_name": model_name,
            "test_category": test_category,
            "valid": False,
            "error": {
                "error_message": [
                    "Error during inference phase. Model did not output a list of model responses."
                ],
                "error_type": "vision_geoguessr:inference_error",
            },
            "prompt": prompt_entry,
            "model_result": model_result_list,
            "possible_answer": possible_answer_item,
        }

    # Try decoding the model results into executable function calls
    # Note: We only care about the last non-function-call message, which should fail to get decoded.
    # We don't care about the function calls in the middle of the conversation.
    # We only check if the expected answer is mentioned in the last message.
    # decode_execute returns a list of strings
    model_result_list_decoded: list[list[str]] = []
    last_unsuccessful_decoding_message = None

    for model_result_item in model_result_list[0]:
        # model_result_item is per step
        try:
            decoded_result: list[str] = handler.decode_execute(
                model_result_item, has_tool_call_tag=False
            )
            if is_empty_execute_response(decoded_result):
                last_unsuccessful_decoding_message = model_result_item
                continue
            model_result_list_decoded.append(decoded_result)
        except Exception as e:
            last_unsuccessful_decoding_message = model_result_item
            continue

    if not last_unsuccessful_decoding_message:
        return {
            "id": index,
            "score": 0.0,
            "model_name": model_name,
            "test_category": test_category,
            "valid": False,
            "error": {
                "error_message": [
                    "Cannot find the last chat message that is not a function call."
                ],
                "error_type": "vision_geoguessr:no_last_message",
            },
            "prompt": prompt_entry,
            "model_result": model_result_list,
            "model_result_decoded": model_result_list_decoded,
            "possible_answer": possible_answer_item,
        }

    # Check if the model output contains the expected answer
    accuracy_checker_result = vision_checker(
        last_unsuccessful_decoding_message,
        possible_answer_item,
    )

    accuracy_checker_result["model_name"] = model_name
    accuracy_checker_result["test_category"] = test_category
    accuracy_checker_result["prompt"] = prompt_entry["question"]
    accuracy_checker_result["model_result_raw"] = model_result_list
    accuracy_checker_result["last_non_fc_message"] = last_unsuccessful_decoding_message
    accuracy_checker_result["possible_answer"] = possible_answer_item

    return accuracy_checker_result


def _evaluate_single_agentic_entry(
    handler: BaseHandler,
    index,
    model_result_list,
    ground_truth: GroundTruth,
    entry: TestEntry,
    model_name,
    test_category,
):
    """Helper method to process a single agentic entry."""
    prompt_entry = _prompt_for_score(entry)
    possible_answer_item = ground_truth.payload

    # Agentic test is a single-turn multi-step test, so the model result should be a list of one element
    if type(model_result_list) != list or len(model_result_list) != 1:
        return {
            "id": index,
            "model_name": model_name,
            "test_category": test_category,
            "valid": False,
            "error": {
                "error_message": [
                    "Error during inference phase. Model did not output a list of model responses."
                ],
                "error_type": "agentic:inference_error",
            },
            "prompt": prompt_entry,
            "model_result": model_result_list,
            "possible_answer": possible_answer_item,
        }

    # Try decoding the model results into executable function calls
    # Note: We only care about the last non-function-call message, which should fail to get decoded.
    # We don't care about the function calls in the middle of the conversation.
    # We only check if the expected answer is mentioned in the last message.
    # decode_execute returns a list of strings
    model_result_list_decoded: list[list[str]] = []
    last_unsuccessful_decoding_message = None

    for model_result_item in model_result_list[0]:
        # model_result_item is per step
        try:
            decoded_result: list[str] = handler.decode_execute(
                model_result_item, has_tool_call_tag=False
            )
            if is_empty_execute_response(decoded_result):
                last_unsuccessful_decoding_message = model_result_item
                continue
            model_result_list_decoded.append(decoded_result)
        except Exception as e:
            last_unsuccessful_decoding_message = model_result_item
            continue

    if not last_unsuccessful_decoding_message:
        return {
            "id": index,
            "model_name": model_name,
            "test_category": test_category,
            "valid": False,
            "error": {
                "error_message": [
                    "Cannot find the last chat message that is not a function call."
                ],
                "error_type": "agentic:no_last_message",
            },
            "prompt": prompt_entry,
            "model_result": model_result_list,
            "model_result_decoded": model_result_list_decoded,
            "possible_answer": possible_answer_item,
        }

    # Check if the model output contains the expected answer
    accuracy_checker_result = agentic_checker(
        last_unsuccessful_decoding_message,
        possible_answer_item,
    )

    if not accuracy_checker_result["valid"]:
        return {
            "id": index,
            "model_name": model_name,
            "test_category": test_category,
            "valid": accuracy_checker_result.pop("valid"),
            "error": accuracy_checker_result,
            "prompt": prompt_entry["question"],
            "model_result_raw": model_result_list,
            "last_non_fc_message": last_unsuccessful_decoding_message,
            "possible_answer": possible_answer_item,
        }

    return {"valid": True}


def _evaluate_single_multi_turn_entry(
    handler: BaseHandler,
    test_entry_id,
    model_result_list,
    ground_truth: GroundTruth,
    entry: TestEntry,
    model_name,
    test_category,
):
    """Helper method to process a single multi-turn entry."""
    prompt_entry = _prompt_for_score(entry)
    ground_truth_list = [list(turn) for turn in ground_truth.turns]

    if type(model_result_list) != list:
        return {
            "id": test_entry_id,
            "model_name": model_name,
            "test_category": test_category,
            "valid": False,
            "error": {
                "error_message": [
                    "Error during inference phase. Model did not output a list of model responses."
                ],
                "error_type": "multi_turn:inference_error",
            },
            "prompt": prompt_entry,
            "model_result": model_result_list,
            "possible_answer": ground_truth_list,
        }

    # Check if force-terminated during inference phase.
    # This happens when the model has retried too many times and still haven't figured out the answer.
    # When force-terminated, no further evaluation is needed. This whole entry will be failed.
    if len(model_result_list) != len(ground_truth_list):
        return {
            "id": test_entry_id,
            "model_name": model_name,
            "test_category": test_category,
            "valid": False,
            "error": {
                "error_message": [
                    f"Model was force-terminated during inference phase. The length of the model result turns ({len(model_result_list)}) does not match the length of the ground truth turns ({len(ground_truth_list)})."
                ],
                "error_type": "multi_turn:force_terminated",
            },
            "prompt": prompt_entry,
            "model_result": model_result_list,
            "possible_answer": ground_truth_list,
        }

    # decode_execute returns a list of strings
    multi_turn_model_result_list_decoded: list[list[list[str]]] = []
    # Try decoding the model results into executable function calls
    for single_turn_model_result_list in model_result_list:
        single_turn_model_result_list_decoded = []
        for model_result_item in single_turn_model_result_list:
            # model_result_item is per step
            try:
                decoded_result: list[str] = handler.decode_execute(
                    model_result_item, has_tool_call_tag=False
                )
                if is_empty_execute_response(decoded_result):
                    # Empty output is not considered as a valid function call
                    continue
                single_turn_model_result_list_decoded.append(decoded_result)
            except Exception as e:
                # Ignore any failed decoding and continue to the next message
                # We only care about the decoded function call, not the error message or if the model is chatting
                continue
        multi_turn_model_result_list_decoded.append(single_turn_model_result_list_decoded)

    # Check if the model output the correct function calls
    accuracy_checker_result = multi_turn_checker(
        multi_turn_model_result_list_decoded,
        ground_truth_list,
        entry,
        model_name,
    )

    if not accuracy_checker_result["valid"]:
        return {
            "id": test_entry_id,
            "model_name": model_name,
            "test_category": test_category,
            "valid": accuracy_checker_result.pop("valid"),
            "error": accuracy_checker_result,
            "prompt": prompt_entry,
            "model_result_raw": model_result_list,
            "model_result_decoded": multi_turn_model_result_list_decoded,
            "possible_answer": ground_truth_list,
        }

    return {"valid": True}


def _evaluate_single_failing_tools_entry(
    handler: BaseHandler,
    index,
    model_result_list,
    ground_truth: GroundTruth,
    entry: TestEntry,
    model_name,
    test_category,
):
    """Helper method to process a single failing_tools entry.

    Failing tools entries are single-turn multi-step interactions.
    The model result is [[step1, step2, ...]] (one turn, multiple steps).
    We decode the function calls and check must_be_called / must_not_be_called constraints.
    """
    prompt_entry = _prompt_for_score(entry)
    if type(model_result_list) != list or len(model_result_list) != 1:
        return {
            "id": index,
            "model_name": model_name,
            "test_category": test_category,
            "valid": False,
            "error": {
                "error_message": [
                    "Error during inference phase. Model did not output a list of model responses."
                ],
                "error_type": "failing_tools:inference_error",
            },
            "prompt": prompt_entry,
            "model_result": model_result_list,
            "possible_answer": ground_truth.payload,
        }

    # Decode model results into executable function calls
    # model_result_list[0] is the single turn's list of steps
    multi_turn_model_result_list_decoded: list[list[list[str]]] = []
    single_turn_model_result_list_decoded = []
    for model_result_item in model_result_list[0]:
        try:
            decoded_result: list[str] = handler.decode_execute(
                model_result_item, has_tool_call_tag=False
            )
            if is_empty_execute_response(decoded_result):
                continue
            single_turn_model_result_list_decoded.append(decoded_result)
        except Exception:
            continue
    multi_turn_model_result_list_decoded.append(single_turn_model_result_list_decoded)

    # Check must_be_called and must_not_be_called constraints
    constraint_result = multi_turn_func_call_constraint_checker(
        multi_turn_model_result_list_decoded,
        ground_truth,
    )
    possible_answer = ground_truth.payload

    if not constraint_result["valid"]:
        return {
            "id": index,
            "model_name": model_name,
            "test_category": test_category,
            "valid": constraint_result.pop("valid"),
            "error": constraint_result,
            "prompt": prompt_entry,
            "model_result_raw": model_result_list,
            "model_result_decoded": multi_turn_model_result_list_decoded,
            "possible_answer": possible_answer,
        }

    return {"valid": True}


def failing_tools_runner(
    handler: BaseHandler,
    model_result,
    prompt,
    possible_answer,
    model_name,
    test_category,
    score_dir,
):
    assert (
        len(model_result) == len(prompt) == len(possible_answer)
    ), f"The length of the model result ({len(model_result)}) does not match the length of the prompt ({len(prompt)}) or possible answer ({len(possible_answer)}). Please check the input files for completeness."

    result = []
    correct_count = 0
    for i in range(len(model_result)):
        index = model_result[i]["id"]
        model_result_list = model_result[i]["result"]

        entry_result = _evaluate_single_failing_tools_entry(
            handler,
            index,
            model_result_list,
            possible_answer[i],
            prompt[i],
            model_name,
            test_category,
        )

        if entry_result["valid"]:
            correct_count += 1
        else:
            entry_result["inference_log"] = model_result[i].get("inference_log", "")
            result.append(entry_result)

    return save_eval_results(
        result,
        correct_count,
        model_result,
        test_category,
        model_name,
        score_dir,
    )


def _evaluate_single_relevance_entry(
    handler: BaseHandler,
    index,
    model_result_item,
    entry: TestEntry,
    model_name,
    test_category,
):
    """Helper method to process a single relevance/irrelevance entry."""
    prompt_entry = entry.to_dict()
    contain_func_call = False
    decoded_result = None
    decode_error = None

    try:
        decoded_result = handler.decode_ast(
            model_result_item, language=ReturnFormat.PYTHON, has_tool_call_tag=False
        )
        # Decode successfully, which means the model output is in valid function call format
        contain_func_call = True
        if is_empty_output(decoded_result):
            # Empty output is not considered as a valid function call
            contain_func_call = False
    except Exception as e:
        # Decode failed, which means the model output is not in valid function call format
        contain_func_call = False
        decode_error = str(e)

    # irrelevance test means no function call outputted
    if "irrelevance" in test_category:
        success = not contain_func_call
    else:
        success = contain_func_call

    if not success:
        temp = {
            "id": index,
            "model_name": model_name,
            "test_category": test_category,
            "valid": success,
            "prompt": prompt_entry,
            "model_result": model_result_item,
            "decoded_result": decoded_result,
        }
        if "irrelevance" in test_category:
            temp["error"] = ["Valid syntax. Successfully decode AST when it should not."]
            temp["error_type"] = "irrelevance_error:decoder_success"
        else:
            temp["error"] = [
                f"Invalid syntax. Failed to decode AST when it should have. {decode_error}"
            ]
            temp["error_type"] = "relevance_error:decoder_failed"
        return temp

    return {"valid": True}


def _evaluate_single_ast_entry(
    handler: BaseHandler,
    index,
    model_result_item,
    ground_truth: GroundTruth,
    entry: TestEntry,
    model_name,
    category: TestCategory,
    language: Language,
    return_format: ReturnFormat,
    has_tool_call_tag=False,
):
    """Helper method to process a single AST entry."""
    prompt_entry = entry.to_dict()
    expected_calls = list(ground_truth.calls)
    # Score files embed the expectation in its on-disk form.
    possible_answer_item = ground_truth.payload
    test_category = category.value

    try:
        model_result_item_raw = model_result_item
        model_result_item = handler.decode_ast(
            model_result_item, return_format, has_tool_call_tag
        )
    except Exception as e:
        return {
            "id": index,
            "model_name": model_name,
            "test_category": test_category,
            "valid": False,
            "error": [f"Invalid syntax. Failed to decode AST. {str(e)}"],
            "error_type": "ast_decoder:decoder_failed",
            "prompt": prompt_entry,
            "model_result_raw": model_result_item_raw,
            "possible_answer": possible_answer_item,
        }

    decoder_output_valid = is_function_calling_format_output(model_result_item)
    if not decoder_output_valid:
        return {
            "id": index,
            "model_name": model_name,
            "test_category": test_category,
            "valid": False,
            "error": [
                "Did not output in the specified format. Note: the model_result is wrapped in a string to ensure json serializability."
            ],
            "error_type": "ast_decoder:decoder_wrong_output_format",
            "prompt": prompt_entry,
            "model_result_raw": str(model_result_item_raw),
            "model_result_decoded": str(model_result_item),
            "possible_answer": possible_answer_item,
        }

    checker_result = ast_checker(
        entry.functions,
        model_result_item,
        expected_calls,
        language,
        category,
        model_name,
    )

    if not checker_result["valid"]:
        return {
            "id": index,
            "model_name": model_name,
            "test_category": test_category,
            "valid": checker_result["valid"],
            "error": checker_result["error"],
            "error_type": checker_result["error_type"],
            "prompt": prompt_entry,
            "model_result_raw": model_result_item_raw,
            "model_result_decoded": model_result_item,
            "possible_answer": possible_answer_item,
        }
    return {"valid": True}



def vision_geoguessr_runner(
    handler: BaseHandler,
    model_result,
    prompt,
    possible_answer,
    model_name,
    test_category,
    score_dir,
):
    assert (
        len(model_result) == len(prompt) == len(possible_answer)
    ), f"The length of the model result ({len(model_result)}) does not match the length of the prompt ({len(prompt)}) or possible answer ({len(possible_answer)}). Please check the input files for completeness."

    result = []
    total_score = 0
    for i in range(len(model_result)):
        index = model_result[i]["id"]
        model_result_list = model_result[i]["result"]

        entry_result = _evaluate_single_vision_geoguessr_entry(
            handler,
            index,
            model_result_list,
            possible_answer[i],
            prompt[i],
            model_name,
            test_category,
        )

        total_score += entry_result["score"]
        entry_result["inference_log"] = model_result[i].get("inference_log", "")
        result.append(entry_result)

    max_score = 5000  # Maximum possible score per entry
    avg_score = total_score / len(model_result)

    scores = [entry["score"] for entry in result]
    if len(scores) > 1:
        score_variance = round(statistics.variance(scores), 2)
        score_std = round(statistics.stdev(scores), 2)
    else:
        score_variance = 0.0
        score_std = 0.0

    extra_header_fields = {
        "score_variance": score_variance,
        "score_std": score_std,
    }

    return save_eval_results(
        result,
        correct_count=total_score,
        model_result=model_result,
        test_category=test_category,
        model_name=model_name,
        score_dir=score_dir,
        accuracy=avg_score / max_score,
        extra_header_fields=extra_header_fields,
    )


def agentic_runner(
    handler: BaseHandler,
    model_result,
    prompt,
    possible_answer,
    model_name,
    test_category,
    score_dir,
):
    assert (
        len(model_result) == len(prompt) == len(possible_answer)
    ), f"The length of the model result ({len(model_result)}) does not match the length of the prompt ({len(prompt)}) or possible answer ({len(possible_answer)}). Please check the input files for completeness."

    result = []
    correct_count = 0
    for i in range(len(model_result)):
        index = model_result[i]["id"]
        model_result_list = model_result[i]["result"]

        entry_result = _evaluate_single_agentic_entry(
            handler,
            index,
            model_result_list,
            possible_answer[i],
            prompt[i],
            model_name,
            test_category,
        )

        if entry_result["valid"]:
            correct_count += 1
        else:
            entry_result["inference_log"] = model_result[i].get("inference_log", "")
            result.append(entry_result)

    return save_eval_results(
        result,
        correct_count,
        model_result,
        test_category,
        model_name,
        score_dir,
    )


def multi_turn_runner(
    handler: BaseHandler,
    model_result,
    prompt,
    possible_answer,
    model_name,
    test_category,
    score_dir,
):
    assert (
        len(model_result) == len(prompt) == len(possible_answer)
    ), f"The length of the model result ({len(model_result)}) does not match the length of the prompt ({len(prompt)}) or possible answer ({len(possible_answer)}). Please check the input files for completeness."

    result = []
    correct_count = 0
    for i in range(len(model_result)):
        index = model_result[i]["id"]
        multi_turn_model_result_list = model_result[i]["result"]

        entry_result = _evaluate_single_multi_turn_entry(
            handler,
            index,
            multi_turn_model_result_list,
            possible_answer[i],
            prompt[i],
            model_name,
            test_category,
        )

        if entry_result["valid"]:
            correct_count += 1
        else:
            entry_result["inference_log"] = model_result[i].get("inference_log", "")
            result.append(entry_result)

    return save_eval_results(
        result,
        correct_count,
        model_result,
        test_category,
        model_name,
        score_dir,
    )


def relevance_file_runner(
    handler: BaseHandler,
    model_result,
    prompt,
    model_name,
    test_category,
    score_dir,
):
    # This function serves for both relevance and irrelevance tests, which share the exact opposite logic.
    # If `test_category` is "irrelevance", the model is expected to output no function call.
    # No function call means either the AST decoding fails (a error message is generated) or the decoded AST does not contain any function call (such as a empty list, `[]`).
    # If `test_category` is "relevance", the model is expected to output to a function call, and empty list doesn't count as a function call.
    result = []
    correct_count = 0
    for i in range(len(model_result)):
        index = model_result[i]["id"]
        model_result_item = model_result[i]["result"]

        entry_result = _evaluate_single_relevance_entry(
            handler, index, model_result_item, prompt[i], model_name, test_category
        )

        if entry_result["valid"]:
            correct_count += 1
        else:
            result.append(entry_result)

    return save_eval_results(
        result,
        correct_count,
        model_result,
        test_category,
        model_name,
        score_dir,
    )


def ast_file_runner(
    handler: BaseHandler,
    model_result,
    prompt: list[TestEntry],
    possible_answer: list[GroundTruth],
    category: TestCategory,
    model_name,
    score_dir,
):
    assert (
        len(model_result) == len(prompt) == len(possible_answer)
    ), f"The length of the model result ({len(model_result)}) does not match the length of the prompt ({len(prompt)}) or possible answer ({len(possible_answer)}). Please check the input files for completeness."

    language = category.language
    return_format = ReturnFormat(language.value)

    result = []
    correct_count = 0
    for i in range(len(model_result)):
        index = model_result[i]["id"]
        model_result_item = model_result[i]["result"]

        entry_result = _evaluate_single_ast_entry(
            handler,
            index,
            model_result_item,
            possible_answer[i],
            prompt[i],
            model_name,
            category,
            language=language,
            return_format=return_format,
            has_tool_call_tag=False,
        )

        if entry_result["valid"]:
            correct_count += 1
        else:
            result.append(entry_result)

    return save_eval_results(
        result,
        correct_count,
        model_result,
        category.value,
        model_name,
        score_dir,
    )


#### Main runner function ####

# Which runner scores which category. Replaces an if/elif chain whose ordering was
# load-bearing -- geoguessr had to be tested before agentic, and vision web search
# before web search, because the predicates were substring matches. A dict has no
# ordering to get wrong.
#
# The AST and relevance strategies are dispatched separately because their runners
# take different arguments: relevance has no ground truth, and the AST runner needs
# the parsed category to pick a language.
_RUNNER_BY_STRATEGY = {
    EvalStrategy.MULTI_TURN_STATE: lambda *a: multi_turn_runner(*a),
    EvalStrategy.SUBSTRING_ANSWER: lambda *a: agentic_runner(*a),
    EvalStrategy.GEO_DISTANCE: lambda *a: vision_geoguessr_runner(*a),
    EvalStrategy.FUNC_CALL_CONSTRAINT: lambda *a: failing_tools_runner(*a),
}

def evaluate_task(
    test_category,
    score_dir,
    model_result,
    model_name,
    handler,
    leaderboard_table,
    allow_missing: bool = False,
):
    tqdm.write(f"🔍 Running test: {test_category}")

    record_cost_latency(leaderboard_table, model_name, test_category, model_result)

    category = TestCategory.parse(test_category)

    # Find the corresponding prompt entries
    prompt = load_dataset_entries(
        category, include_prereq=False, include_language_specific_hint=False
    )

    if category.ground_truth_kind is GroundTruthKind.NONE:
        # relevance / irrelevance: scored purely on whether a call was emitted.
        possible_answer = []
        prompt, _ = _subset_entries_by_model_ids(
            model_result, prompt, None, allow_missing=allow_missing
        )
    elif category.is_vision:
        possible_answer = load_ground_truth_entries(category)
        # NOTE: the vision categories deliberately skip subsetting, so --partial-eval
        # does not apply to them and the runners' length assertion fires instead.
        # Preserved as-is. The ground truth is now complete -- vision_base.json holds
        # all 250 entries, restored from the `vision` branch -- so that assertion
        # passes for every vision web-search category.
    else:
        # @HuanzhiMao TODO: check if this works for audio cases.
        possible_answer = load_ground_truth_entries(category)
        # Sanity: prompt and ground truth should be 1:1
        assert len(prompt) == len(
            possible_answer
        ), f"Length of ground truth ({len(possible_answer)}) should match prompt entries ({len(prompt)})."

        prompt, possible_answer = _subset_entries_by_model_ids(
            model_result, prompt, possible_answer, allow_missing=allow_missing
        )

    if category.eval_strategy is EvalStrategy.RELEVANCE:
        accuracy, total_count = relevance_file_runner(
            handler, model_result, prompt, model_name, test_category, score_dir
        )
    elif category.eval_strategy in AST_STRATEGIES:
        accuracy, total_count = ast_file_runner(
            handler, model_result, prompt, possible_answer, category, model_name, score_dir
        )
    else:
        runner_fn = _RUNNER_BY_STRATEGY[category.eval_strategy]
        accuracy, total_count = runner_fn(
            handler, model_result, prompt, possible_answer, model_name, test_category, score_dir
        )

    record_result(leaderboard_table, model_name, test_category, accuracy, total_count)

    tqdm.write(f"✅ Test completed: {test_category}. 🎯 Accuracy: {accuracy:.2%}")

    return leaderboard_table


def runner(
    model_names, test_categories, result_dir, score_dir, allow_missing: bool = False
):

    # A dictionary to store the evaluation scores.
    # Key is model name, value is a dictionary with keys as test category
    # and values as a dictionary with accuracy and total count.
    leaderboard_table = {}

    # Get a list of all entries in the folder
    entries = result_dir.iterdir()

    # Filter out the subdirectories
    subdirs = [entry for entry in entries if entry.is_dir()]

    # Traverse each subdirectory
    for subdir in tqdm(subdirs, desc="Number of models evaluated", position=0):

        model_name = subdir.relative_to(result_dir).name
        if model_names is not None and model_name not in model_names:
            continue

        registry_name = DIR_NAME_TO_REGISTRY.get(model_name)
        if registry_name is None:
            tqdm.write(
                f"⚠️  Skipping directory '{model_name}': no matching model found in MODEL_CONFIG_MAPPING."
            )
            continue

        tqdm.write(f"🦍 Model: {model_name}")

        # Find and process all result JSON files recursively in the subdirectory
        for model_result_json in subdir.rglob(RESULT_FILE_PATTERN):
            print(model_result_json)
            base_category = extract_test_category(model_result_json)
            print(base_category)
            # Reconstruct the full prefixed category name from the directory structure
            modality = detect_modality_from_path(model_result_json, subdir)
            print(modality)
            # raise Exception
            test_category = f"{modality}:{base_category}"
            if test_category not in test_categories:
                continue

            handler = get_handler(registry_name)

            # We don't evaluate the following categories in the current iteration of the benchmark
            if (
                is_chatable(test_category)
                or is_sql(test_category)
                or is_executable(test_category)
                or is_memory_prereq(test_category)
            ):
                continue

            model_result = load_file(model_result_json, sort_by_id=True)

            leaderboard_table = evaluate_task(
                test_category,
                score_dir,
                model_result,
                model_name,
                handler,
                leaderboard_table,
                allow_missing=allow_missing,
            )

    # This function reads all the score files from local folder and updates the
    # leaderboard table. This is helpful when you only want to run the
    # evaluation for a subset of models and test categories.
    update_leaderboard_table_with_local_score_file(leaderboard_table, score_dir)
    # Write the leaderboard table to a file
    generate_leaderboard_csv(leaderboard_table, score_dir)


def main(model, test_categories, result_dir, score_dir, partial_eval: bool = False):
    if result_dir is None:
        result_dir = RESULT_PATH
    else:
        result_dir = (PROJECT_ROOT / result_dir).resolve()

    if score_dir is None:
        score_dir = SCORE_PATH
    else:
        score_dir = (PROJECT_ROOT / score_dir).resolve()

    if type(test_categories) is not list:
        test_categories = [test_categories]

    all_test_categories = parse_test_category_argument(test_categories)

    model_names = None
    if model:
        model_names = []
        for model_name in model:
            if model_name not in MODEL_CONFIG_MAPPING:
                raise ValueError(f"Invalid model name '{model_name}'.")
            # Look up the pre-computed sanitized directory name from model_config.
            model_names.append(REGISTRY_TO_DIR_NAME[model_name])

    # Driver function to run the evaluation for all categories involved.
    runner(
        model_names,
        all_test_categories,
        result_dir,
        score_dir,
        allow_missing=partial_eval,
    )

    tqdm.write(
        f"🏁 Evaluation completed. See {score_dir / 'score_overall.csv'} for cross-modality overall results on BFCL V4."
    )
    if partial_eval:
        tqdm.write(
            "⚠️  Partial evaluation for a single category is enabled (--partial-run flag is set). Accuracy scores are computed only on the subset of entries present in the model result files, which may differ from a full evaluation and from the official leaderboard score."
        )
    tqdm.write(
        f"See {score_dir / 'score_text_overall.csv'} for text modality details, "
        f"{score_dir / 'score_true_audio_overall.csv'} and {score_dir / 'score_text_audio_overall.csv'} for audio, "
        f"and {score_dir / 'score_vision_overall.csv'} for vision."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process two lists of strings.")

    # Add arguments for two lists of strings
    parser.add_argument(
        "--model", nargs="+", type=str, help="A list of model names to evaluate"
    )
    parser.add_argument(
        "--test-category",
        nargs="+",
        type=str,
        default="all",
        help="A list of test categories to run the evaluation on",
    )
    parser.add_argument(
        "--result-dir",
        default=None,
        type=str,
        help="Path to the folder where the model response files are stored; relative to the `berkeley-function-call-leaderboard` root folder",
    )
    parser.add_argument(
        "--score-dir",
        default=None,
        type=str,
        help="Path to the folder where the evaluation score files will be stored; relative to the `berkeley-function-call-leaderboard` root folder",
    )
    parser.add_argument(
        "--partial-eval",
        default=False,
        action="store_true",
        help="Run evaluation on a partial set of benchmark entries (eg. entries present in the model result files) without raising for missing IDs.",
    )

    args = parser.parse_args()

    load_dotenv(dotenv_path=DOTENV_PATH, verbose=True, override=True)  # Load the .env file
    main(
        args.model,
        args.test_category,
        args.result_dir,
        args.score_dir,
        partial_eval=args.partial_eval,
    )
