from bfcl.eval_checker.multi_turn_eval.multi_turn_utils import execute_multi_turn_func_call
from bfcl.eval_checker.eval_runner_helper import load_file, write_list_of_dicts_to_file
from bfcl._llm_response_generation import process_multi_turn_test_case

INITIAL_CONFOG_MAPPING = {
    "GorillaFileSystem": ["root"],
    "MessageAPI": ["random_seed", "generated_ids", "user_count", "user_map", "inbox", "message_count", "current_user"],
    "TwitterAPI": ["username", "password", "authenticated", "tweets", "comments", "retweets", "following_list", "tweet_counter"],
    "TicketAPI": ["ticket_queue", "ticket_counter", "current_user"],
    "TradingBot": ["orders", "account_info", "authenticated", "market_status", "order_counter", "stocks", "watch_list", "transaction_history"],
    "TravelAPI": ["random_seed", "credit_card_list", "booking_record", "access_token", "token_type", "token_expires_in", "token_scope", "user_first_name", "user_last_name", "budget_limit"],
    "VehicleControlAPI": ["random_seed", "fuelLevel", "batteryVoltage", "engineState", "remainingUnlockedDoors", "doorStatus", "acTemperature", "fanSpeed", "acMode", "humidityLevel", "headLightStatus", "brakeStatus", "brakeForce", "slopeAngle", "distanceToNextVehicle", "cruiseStatus", "destination", "frontLeftTirePressure", "frontRightTirePressure", "rearLeftTirePressure", "rearRightTirePressure"],
}

"MathAPI"
ground_truth_data = load_file("../data/possible_answer/BFCL_v3_multi_turn_base.json")
dataset_data = load_file("../data/BFCL_v3_multi_turn_base.json")
# dataset_data = process_multi_turn_test_case(dataset_data, "multi_turn_base")
result = []
for ground_truth_entry, test_entry in zip(ground_truth_data, dataset_data):
    entry_result = {"id": test_entry["id"], "affected_classes": []}
    initial_configs = test_entry["initial_config"]
    involved_classes = test_entry["involved_classes"]
    for class_name in involved_classes:
        if class_name == "MathAPI":
            continue
        if class_name not in initial_configs:
            continue
        
        initial_config = initial_configs[class_name]
        temp = {str(class_name): []}
        for key in initial_config.keys():
            if key not in INITIAL_CONFOG_MAPPING[class_name]:
                temp[str(class_name)].append(key)
        if len(temp[str(class_name)]) > 0:
            entry_result["affected_classes"].append(temp)
    entry_result.update(test_entry)
    entry_result["possible_answer"] = ground_truth_entry["ground_truth"]
    if len(entry_result["affected_classes"]) > 0:
        result.append(entry_result)

write_list_of_dicts_to_file("initial_config_result.json", result)