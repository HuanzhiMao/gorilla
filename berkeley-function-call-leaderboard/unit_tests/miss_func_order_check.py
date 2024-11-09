from bfcl.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
from bfcl.eval_checker.eval_runner_helper import load_file, write_list_of_dicts_to_file
from bfcl._llm_response_generation import process_multi_turn_test_case

ground_truth_data = load_file("../data/possible_answer/BFCL_v3_multi_turn_miss_func.json")
dataset_data = load_file("../data/BFCL_v3_multi_turn_miss_func.json")
result = []
for ground_truth_entry, test_entry in zip(ground_truth_data, dataset_data):
    ground_truth_answer = ground_truth_entry["ground_truth"]
    questions = test_entry["question"]
    for idx, ans in enumerate(ground_truth_answer):
        if ans == []:
            ans_idx = idx
    for idx, ques in enumerate(questions):
        if ques == []:
            ques_idx = idx
    if ques_idx - 1 != ans_idx:
        print(ground_truth_entry["id"])
