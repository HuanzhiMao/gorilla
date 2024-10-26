import json
import os

from anthropic import Anthropic
from bfcl._llm_response_generation import process_multi_turn_test_case
from bfcl.constant import DOTENV_PATH
from bfcl.eval_checker.eval_runner_helper import load_file, write_list_of_dicts_to_file
from bfcl.eval_checker.multi_turn_eval.multi_turn_utils import (
    execute_multi_turn_func_call,
)
from dotenv import load_dotenv

load_dotenv(DOTENV_PATH, override=True) 
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
SYSTEM_PROMPT = """This is the initial config of a fake TwitterAPI class. Help me complete it with three items:
- username: the username of the user.
- password: the password of the user, could be a random string.
- tweets: a list of tweets that the user has posted; dictionaries of dictionaries, where the key is the tweet id (from 0), and the value is a TWEET Object. 

The content of the tweets will be given to you in the user prompt. You should turn each tweet content into a TWEET Object (dictionary) with the following keys:
- id: the unique id of the tweet, an integer, starting from 0
- username: the username of the user who posted the tweet, which should be the same throughout all the tweets, and the same as the username in the initial config
- content: the content of the tweet, which is given in the input
- tags: a list of tags that are included in the tweet, a list of strings. each tag should start with a "#" symbol
- mentions: a list of mentions that are included in the tweet, a list of strings. each mention should start with a "@" symbol

You can make up the details as you see fit, in a real-world scenario. 
Your return should be in valid json format.
"""
def call_openai(msg):
    api_response =  client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=8192,
        temperature=0.7,
        system=SYSTEM_PROMPT,
        messages=msg,
    )
    return api_response
INITIAL_CONFOG_MAPPING = {
    "GorillaFileSystem": ["root"],
    "MessageAPI": ["random_seed", "generated_ids", "user_count", "user_map", "inbox", "message_count", "current_user"],
    "TwitterAPI": ["username", "password", "authenticated", "tweets", "comments", "retweets", "following_list", "tweet_counter"],
    "TicketAPI": ["ticket_queue", "ticket_counter", "current_user"],
    "TradingBot": ["orders", "account_info", "authenticated", "market_status", "order_counter", "stocks", "watch_list", "transaction_history"],
    "TravelAPI": ["random_seed", "credit_card_list", "booking_record", "access_token", "token_type", "token_expires_in", "token_scope", "user_first_name", "user_last_name", "budget_limit"],
    "VehicleControlAPI": ["random_seed", "fuelLevel", "batteryVoltage", "engineState", "remainingUnlockedDoors", "doorStatus", "acTemperature", "fanSpeed", "acMode", "humidityLevel", "headLightStatus", "brakeStatus", "brakeForce", "slopeAngle", "distanceToNextVehicle", "cruiseStatus", "destination", "frontLeftTirePressure", "frontRightTirePressure", "rearLeftTirePressure", "rearRightTirePressure"],
}

ground_truth_data = load_file("../data/possible_answer/BFCL_v3_multi_turn_base.json")
dataset_data = load_file("../data/BFCL_v3_multi_turn_base.json")
# dataset_data = process_multi_turn_test_case(dataset_data, "multi_turn_base")
result = []
for ground_truth_entry, test_entry in zip(ground_truth_data, dataset_data):
    entry_result = {"id": test_entry["id"], "affected_classes": []}
    initial_configs = test_entry["initial_config"]
    involved_classes = test_entry["involved_classes"]
    for class_name in involved_classes:
        if class_name != "TwitterAPI":
            continue
        if class_name == "MathAPI":
            continue
        if class_name not in initial_configs:
            continue
        
        initial_config = initial_configs[class_name]
        if "tweets" in initial_config and len(initial_config["tweets"]) > 0:
            tweets = initial_config["tweets"]
            query_str = f"Here are the tweets that the user has posted: {tweets}"
            if "username" in initial_config:
                query_str += f"\n\nThe username of the user is {initial_config['username']}; you should not change this in the initial config."
            if "password" in initial_config:
                query_str += f"\n\nThe password of the user is {initial_config['password']}; you should not change this in the initial config."
            api_response = call_openai([{"role": "user", "content": query_str}])
            api_response = api_response.content[0].text
            try:
                api_response = json.loads(api_response)
                initial_configs[class_name].update(api_response)
                print("--------------------")
                print(api_response)
                print("\n\n")
                print(initial_configs[class_name])
                print("\n\n")
            except:
                print(api_response)
                print(test_entry["id"])


write_list_of_dicts_to_file("../data/BFCL_v3_multi_turn_base.json", dataset_data)