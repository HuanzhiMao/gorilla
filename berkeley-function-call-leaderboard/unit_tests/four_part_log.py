from bfcl.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
from bfcl.eval_checker.eval_runner_helper import load_file, write_list_of_dicts_to_file
from bfcl._llm_response_generation import process_multi_turn_test_case

ground_truth_data = load_file("../data/possible_answer/BFCL_v3_multi_turn_base.json")
dataset_data = load_file("../data/BFCL_v3_multi_turn_base.json")
# dataset_data = process_multi_turn_test_case(dataset_data, "multi_turn_base")
result = []
for ground_truth_entry, test_entry in zip(ground_truth_data, dataset_data):
    entry_result = {"id": test_entry["id"], "log": [{"initial_config": test_entry["initial_config"]}]}
    for index, turn in enumerate(ground_truth_entry["ground_truth"]):

        execution_results, involved_instances =execute_multi_turn_func_call(
            func_call_list=turn,
            initial_config=test_entry["initial_config"],
            involved_classes=test_entry["involved_classes"],
            model_name= "ground_truth",
            test_entry_id=test_entry["id"],
            long_context=False,
            is_evaL_run=False,
        )

        ground_truth_instance_attributes = [{
            key: value
            for key, value in vars(z).items()
            if not key.startswith("_")
        } for z in involved_instances.values()]

        # entry_result["log"].append([{"model instance": [], "ground truth instance": ground_truth_instance_attributes}])
        entry_result["log"].append({"Question": test_entry["question"][index]})
        for item, item_result in zip(ground_truth_entry["ground_truth"][index], execution_results): 
            entry_result["log"].append({"func_call": item, "result": item_result})
            

    # entry_result.update(test_entry)
    # entry_result["possible_answer"] = ground_truth_entry["ground_truth"]
    result.append(entry_result)

write_list_of_dicts_to_file("ground_truth_result_hans.json", result)