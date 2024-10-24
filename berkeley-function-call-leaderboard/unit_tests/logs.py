import os
import sys
notebook_dir = os.getcwd()
parent_dir = os.path.dirname(notebook_dir)
sys.path.append(parent_dir)

from collections import defaultdict
from copy import deepcopy
import textwrap
from typing import List, Dict, Any
from collections import Counter
import json

INPUT_FILE = f"ground_truth_result.json"

with open(INPUT_FILE, "r") as f:
    data = [json.loads(line) for line in f.readlines()[1:]]
    
notebook_dir = os.getcwd()
parent_dir = os.path.dirname(notebook_dir)
sys.path.append(parent_dir)


MODEL_FAILED_KEYWORDS = [
    "issue",
    "couldn't",
    "could not",
    "can't",
    "cannot",
    "does not",
    "doesn't",
    "further assistance",
    "sorry",
    "apologize",
]

def process_json_log(data: List[Dict[str, Any]]) -> None:
    for log_entry in data:
        print_formatted_info(log_entry)
        print_model_result_stats(log_entry)

    print_failure_mode_analysis(data)


def print_dict(d: Dict[str, Any], indent: int = 0) -> None:
    for key, value in d.items():
        print(" " * indent + f"\"{key}\":")
        if isinstance(value, dict):
            print_dict(value, indent + 4)
        else:
            print(" " * (indent + 4) + f"- {value}")


main_apis = ["GorillaFileSystem",
             "VehicleControlAPI", "TradingBot", "TravelAPI"]


def get_main_api(involved_apis: List[str]) -> str:
    for api in involved_apis:
        if api in main_apis:
            return api
    return "N/A"


def print_formatted_info(log_entry: Dict[str, Any]) -> None:
    if "log" not in log_entry:
        return
    log_idx = log_entry.get('id', 'N/A')
    model_results = []
    possible_answers = log_entry["possible_answer"]
    questions = log_entry["question"]
    initial_config = log_entry["initial_config"]
    involved_apis = log_entry["involved_classes"]
    execution_states = log_entry["log"][::2]
    execution_responses = log_entry["log"][1::2]
    error = log_entry.get("error", "N/A")
    error_type = log_entry.get("error_type", "N/A")
    print(f"🆔: {log_idx}")
    if error != "N/A":
        if "details" in error:
            print(f"❗️❗️❗️Error Details: {json.dumps(error['details'])}")
        print(f"❗️❗️❗️Error Type: {error_type}")
    print(f"Model Name: {log_entry.get('model_name', 'N/A')}")
    print(f"Main API Classes: {get_main_api(involved_apis)}")
    print(f"Test Category: {log_entry.get('test_category', 'N/A')}")
    # print("# 🥩Raw Initial Config (Generated)")
    try:
        for key, value in initial_config.items():
            print(f"API: {key}")
            print("    Initial Config:")
            print_dict(value, indent=8)
    except Exception as e:
        print(f"❗️7️⃣WARNING:INITIAL_CONFIG:UNEXPECTED_FORMAT {e}, check the initial config for correctness")
        
    print("\n# Model Results and Possible Answers")

    column_width = 80
    max_turns = len(questions)
    for i in range(max_turns):
        print(f"\nTurn {i+1}:")
        # Increased width for the new column
        print("-" * (column_width * 2 + 13))
        if questions[i]:
            print(f"Question: {questions[i][0]['content']}")
        else:
            print(f"Question: N/A")
        print("-" * (column_width * 2 + 13))
        print("Calls | Model Response".ljust(column_width + 8) +
              "| Possible Answer (Human Labeled Ground Truth)")
        print("-" * (column_width * 2 + 13))

        # Only print the model function calls and possible answers if the turn is not empty
        if i < len(possible_answers) or i < len(model_results):
            model_turn = []
            possible_turn = possible_answers[i] if i < len(
                possible_answers) else []

            max_items = max(len(model_turn) - 1, len(possible_turn))

            for j in range(max_items):
                model_lines = []
                possible_lines = []

                if j < len(model_turn) - 1:
                    item = model_turn[j]
                    if isinstance(item, dict):
                        for func, args in item.items():
                            func_call = f"{func}({args})"
                            model_lines = textwrap.wrap(
                                func_call, width=column_width-1)
                    else:
                        model_lines = textwrap.wrap(
                            str(item), width=column_width-1)

                if j < len(possible_turn):
                    possible_lines = textwrap.wrap(
                        possible_turn[j], width=column_width-1)

                max_lines = max(len(model_lines), len(possible_lines))

                for k in range(max_lines):
                    model_line = model_lines[k] if k < len(model_lines) else ""
                    possible_line = possible_lines[k] if k < len(
                        possible_lines) else ""
                    call_count = str(j+1) if k == 0 else ""
                    print(f"{call_count:5} | {model_line.ljust(column_width)}| {possible_line}")

        else:
            print("DEBUGGING", i, len(model_results), len(possible_answers))
        print("\nExecution Responses:")
        print("-" * (column_width * 2 + 13))
        print("Call | Model Generated".ljust(
            column_width + 8) + "| Human Ground Truth")
        print("-" * (column_width * 2 + 13))

        if i < len(execution_responses):
            model_responses = execution_responses[i][0].get(
                'model response', [])
            ground_truth_responses = execution_responses[i][0].get(
                'ground truth response', [])

            max_responses = max(len(model_responses),
                                len(ground_truth_responses))

            for j in range(max_responses):
                model_response = model_responses[j] if j < len(
                    model_responses) else ""
                ground_truth_response = ground_truth_responses[j] if j < len(
                    ground_truth_responses) else ""

                model_lines = textwrap.wrap(
                    str(model_response), width=column_width-1)
                ground_truth_lines = textwrap.wrap(
                    str(ground_truth_response), width=column_width-1)

                max_lines = max(len(model_lines), len(ground_truth_lines))

                for k in range(max_lines):
                    model_line = model_lines[k] if k < len(model_lines) else ""
                    ground_truth_line = ground_truth_lines[k] if k < len(
                        ground_truth_lines) else ""
                    call_count = str(j+1) if k == 0 else ""
                    print(f"{call_count:5} | {model_line.ljust(column_width)}| {ground_truth_line}")

                if j < max_responses - 1:
                    # Separator between calls
                    print("-" * (column_width * 2 + 13))
            if is_response_with_error(model_responses):
                print(f"❗️3️⃣WARNING:EXECUTION_RESPONSE:ERROR_IN_EXECUTION_RESPONSE Error in execution response for index {log_idx} turn {i+1}")

            if is_response_with_error(ground_truth_responses):
                print(f"❗️❗️❗️4️⃣WARNING:EXECUTION_RESPONSE:ERROR_IN_GROUND_TRUTH_RESPONSE Error in ground truth response for index {log_idx} turn {i+1}")

        print("\n" + "=" * (column_width * 2 + 13))
        print("Execution States:")
        print("-" * (column_width * 2 + 13))
        print("Model Generated".ljust(column_width) + "| Human Ground Truth")
        print("-" * (column_width * 2 + 13))

        if i < len(execution_states):
            model_state = execution_states[i][0].get('model instance', {})
            ground_truth_state = execution_states[i][0].get(
                'ground truth instance', {})

            model_lines = textwrap.wrap(str(model_state), width=column_width-1)
            ground_truth_lines = textwrap.wrap(
                str(ground_truth_state), width=column_width-1)

            max_lines = max(len(model_lines), len(ground_truth_lines))

            for j in range(max_lines):
                model_line = model_lines[j] if j < len(model_lines) else ""
                ground_truth_line = ground_truth_lines[j] if j < len(
                    ground_truth_lines) else ""
                print(f"{model_line.ljust(column_width)}| {ground_truth_line}")

        print("\n" + "=" * (column_width * 2 + 13))  # Separator between turns


def is_response_with_error(responses):
    for response in responses:
        try:
            response = json.loads(response)
            if isinstance(response, dict):
                if "error" in response.keys():
                    return True
        except Exception as e:
            if "error" in response.lower():
                return True
    return False


def print_model_result_stats(log_entry: Dict[str, Any]) -> None:
    model_results = []
    possible_answers = log_entry["possible_answer"]
    questions = log_entry["question"]

    def count_function_calls(turn):
        count = 0
        for item in turn:
            if isinstance(item, dict):
                count += 1
            elif isinstance(item, list):
                count += sum(1 for sub_item in item if isinstance(sub_item, dict))
        return count

    model_turn_lengths = [count_function_calls(turn) for turn in model_results]
    possible_answer_turn_lengths = [len(turn) for turn in possible_answers]

    print("Model Result Statistics:")
    print(f"Total turns: {len(model_results)}")
    print(f"Model function calls per turn: {model_turn_lengths}")
    print(f"Possible answer function calls per turn: {possible_answer_turn_lengths}")

    if len(questions) != len(possible_answers):
        print(f"❗️❗️❗️5️⃣WARNING:HUMAN_LABELER Number of question turns ({len(questions)}) does not match number of human labeled possible answers ({len(possible_answers)})")

    if model_turn_lengths:
        print(
            f"Average model function calls per turn: {sum(model_turn_lengths) / len(model_turn_lengths):.2f}"
        )
        print(f"Max model function calls in a turn: {max(model_turn_lengths)}")
        print(f"Min model function calls in a turn: {min(model_turn_lengths)}")
    else:
        print("No model function calls recorded.")

    if possible_answer_turn_lengths:
        print(
            f"Average possible answer function calls per turn: {sum(possible_answer_turn_lengths) / len(possible_answer_turn_lengths):.2f}"
        )
        print(
            f"Max possible answer function calls in a turn: {max(possible_answer_turn_lengths)}"
        )
        print(
            f"Min possible answer function calls in a turn: {min(possible_answer_turn_lengths)}"
        )
    else:
        print("No possible answer function calls recorded.")

    print("\n" + "=" * 80 + "\n")


def print_failure_mode_analysis(data: List[Dict[str, Any]]) -> None:
    error_types = [log_entry.get("error_type", "N/A") for log_entry in data]
    error_counts = Counter(error_types)
    total_errors = len(error_types)

    print("Failure Mode Analysis:")
    for error_type, count in error_counts.items():
        percentage = (count / total_errors) * 100
        print(f"{error_type}: {count} occurrences ({percentage:.2f}%)")

    # Count errors for each API class
    api_error_counts = defaultdict(int)
    for log_entry in data:
        error = log_entry.get("error")
        error_type = log_entry.get("error_type")
        if error != "N/A" or error_type != "N/A":
            involved_apis = log_entry["involved_classes"]
            api_classes = get_main_api(involved_apis)
            api_error_counts[api_classes] += 1

    print("\nErrors per API class:")
    for api_class, count in api_error_counts.items():
        print(f"{api_class}: {count} errors")


if __name__ == "__main__":
    process_json_log(data)