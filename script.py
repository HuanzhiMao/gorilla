import json
import sys
from openai import OpenAI
import os
from datetime import datetime
from tqdm import tqdm
from openai import AzureOpenAI
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from argparse import ArgumentParser
import threading

"""
script for cleaning live_multiple. it decouples the relevant ground_truth function document for prompting and also shows it in the output json so you can essentially treat multiple as simple

In other categories we observed some ground truth issues. One example from the AST category is "Please find me a therapist in Pittsburg that is a psychiatrist.". The allowed answer is [{'Services_4_FindProvider': {'city': ['Pittsburg, PA'], 'type': ['Psychiatrist'], 'accepts_insurance': ['', False]}}]. However, Pittsburg is a city in CA while Pittsburgh is a city in PA. Another example is "I'm craving Asian Fusion cuisine. Can you search for a restaurant in Santa Clara that serves this type of food?", the allowed answer is [{'Restaurants_2_FindRestaurants': {'category': ['Asian'], 'location': ['Santa Clara, CA'], 'price_range': ['', 'moderate'], 'has_vegetarian_options': ['', False], 'has_seating_outdoors': ['', False]}}]. The category is set to Asian, but not Asian Fusion. IMHO, the answers to the prompts should be unambiguous and accurate since we are using the string match for parameter value. If you are open to accept data fixes/contributions, we are happy to screen the prompts/answers to make the benchmark more trustworthy and robust.

"""


# Setting up argument parser
argparser = ArgumentParser()
argparser.add_argument("--ckpt", type=str)

args = argparser.parse_args()
now = datetime.now()
current_time = now.strftime("%b%d_%I%M%p")

# Set up the OpenAI Azure client
client = AzureOpenAI(
    azure_endpoint="https://gorilla2.openai.azure.com/",
    api_key="596fcb8cd12747f8bf6a4ebb318bab49",
    api_version="2023-12-01-preview",
)
MODEL_IN_USE = "gorilla-4-1106"

def write_list_of_dicts_to_file(filename, data, subdir=None, appendMode=False):
    if subdir:
        os.makedirs(subdir, exist_ok=True)
        filename = os.path.join(subdir, filename)

    with open(filename, "a" if appendMode else "w") as f:
        for entry in data:
            json_str = json.dumps(entry)
            f.write(json_str)
            f.write("\n")

def get_openai_response(message, client, MODEL_IN_USE):
    response = client.chat.completions.create(
        model=MODEL_IN_USE,
        messages=message,
        temperature=0.7,
        top_p=0.95,
        timeout=100,
        response_format={"type": "json_object"},
    )
    return response.choices[0].message.content

rating_prompt = """
I need to provide a rating based on whether the prompt and function document need to be reevaluated by a human. Here is a set of key criteria to look at to come up with this rating.
Answer in JSON format, with two fields: 'rating' and 'explanation'.
```
You don't need to rate for system prompts that is in json of {'role': 'assistant', 'content': ...}
Only rate for {'role': 'user', 'content': ...}
Rating for a human to re-evaluate is higher if one or many of these cases are seen:
1. Ambiguous User Prompt (MOST IMPORTANT!!!!)
If the user prompt is not clear enough, then there can be many different ways of calling functions to answer the user. This is not ideal and such a prompt needs reevaluation.
Eg. User: "Find good reputation professional cleaning in Bangkok".
This is unclear. We don't know what does 'good' mean? This example would merit a human to reevaluathe the prompt. A better user prompt would be: "Find good reputation professional cleaning in Bangkok with rating of 8 and above out of 10." Such a user response is more specific.
2. Ambiguous Function description:
If the description of a function is not clear or misleading, then it is difficult to figure out which functions need to be called to answer the user. This is not ideal and such a function needs reevaluation.
3. Ambiguous Function Parameter Description:
If the description of the parameter of a function is not clear or misleading, then it is difficult to figure out what should the function parameters be in order to call the function correctly to answer the user. This is not ideal and such a function parameter needs reevaluation.
Eg.   {"name": "get_weather", "description": "Gives the weather conditions for a given place", "parameters": {"type": "dict", "required": ["location"], "properties": {"location": {"type": "string", "description": "Location in city, state format"}}}}]}
The parameter description for location is unclear. It says that it wants the location in the city, state format. But this is ambiguous. Is Berkeley, CA valid, or Berkeley, California?? Instead if the description for the location parameter would be: Location in (city name, full name of state) format, then there is no ambiguity.
```
Output your ratings in JSON format, with two fields: 'rating' and 'explanation'. For explanation, avoid too many breaklines, give well-formatted outputs. Don't be too elaborate, SUMMARIZE your point, be DIRECT and SUCCINT.
NOTE:
The user prompt, function description and function parameter descriptions should be so specific that there is only one possible function call or sequence of function calls that can answer the query. If you think this isn't the case for the given user prompt and function document, then you must give a high rating.
Eg.
{
    "id": "live_simple_15-3-11",
    "question": [
        [
            {
                "role": "user",
                "content": "I'm at Tamil Nadu. Tell me the current weather conditions in Chennai"
            }
        ]
    ],
    "function": [
        {
            "name": "get_current_weather",
            "description": "Retrieves the current weather conditions for a specified city and state in ahrenheit",
            "parameters": {
                "type": "dict",
                "required": [
                    "location"
                ],
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The location for which to get the weather, in the format of 'City, State', such as 'San Francisco, CA' if State for the city exists. 'City, Country' if State for the city doesn't exist."
                    },
                    "unit": {
                        "type": "string",
                        "description": "The unit of temperature for the weather report.",
                        "enum": [
                            "celsius",
                            "fahrenheit"
                        ],
                        "default": "fahrenheit"
                    }
                }
            }
        }
    ]
}
The user prompt can be solved in many ways. get_current_weather("Chennai", "fahrenheit"), get_current_weather("Chennai", "celsius"), get_current_weather("Chennai"). This is not good. Instead if the user prompt had been "I'm at Tamil Nadu. Tell me the current weather conditions in Chennai in celsius" then there is only one possible way of answering the user: get_current_weather("Chennai", "celsius"). This case would require human re-evaluation and should be rated very high.
Give the rating (integer type) from 0 (lowest) to 5 (highest) based on the above criteria. Only rate for {'role': 'user', 'content': ...} (semantically with the function doc). Please provide a detailed explanation for your rating. 0 is given when the prompt, or function docs don't need any human re-evaluation and is very clear. 5 is given when the prompt and/or the function docs are completely unclear and ambiguous, it is very difficult to propose a function call and parameters that will answer the user query. Such a case would require extensive human re-evaluation.
Don't penalize rating points if the user prompt, function description, or parameter description is in a language apart from English.
"""


def get_prompt(function_doc, user_prompt, PROMPT):
    """Generate a message format for prompt evaluation."""

    # Constructing the message with system and user roles for prompt evaluation
    message = [
        {"role": "system", "content": PROMPT},
        {
            "role": "user",
            "content": f"""
            Function(s) defined as follows:
            {function_doc}
            
            Prompt defined as follows:
            {user_prompt}
            """
        }
    ]
    return message

def rating_judge(function_doc, user_prompt):
    """Judge the quality of the prompt and function document."""
    message = get_prompt(function_doc, user_prompt, PROMPT=rating_prompt)
    response = get_openai_response(message, client, MODEL_IN_USE)
    js =  json.loads(response)
    return js["rating"], js["explanation"]

def load_jsonl(file_path):
    with open(file_path, 'r') as file:
        return [json.loads(line) for line in file]
def hi():
    data = load_jsonl("./berkeley-function-call-leaderboard/data/possible_answer/BFCL_v3_live_multiple.json")
    dic = {}
    for d in data:
        dic[d["id"]] = list(d["ground_truth"][0].keys())[0]
    return dic



def save_jsonl(data, file_path):
    with open(file_path, 'w') as file:
        for entry in data:
            file.write(json.dumps(entry) + '\n')

ground_truths = hi()
    

def process_entry(doc, OUTPUT_FILE, OUTPUT_FILE_NAME):
    """Process a single entry and retrieve the rating for the user prompt."""
    print("Processing  ", doc["id"])
    worker_id = threading.current_thread().name.split("_")[-1]
    INTERMEDIATE_FILE = os.path.join(
        INTERMEDIATE_DIRECTORY, OUTPUT_FILE_NAME[:-5] + f"intermediate_{worker_id}.json"
    )

    real_doc = None
    for f in doc["function"]:
        if f["name"] == ground_truths[doc["id"]]:
            real_doc = f
            break
    rating, explanation = rating_judge(real_doc, doc["question"])
    output_json = {
        "id": doc["id"],
        "ground": ground_truths[doc["id"]],
        "score": rating,
        "explanation": explanation,
        "question": doc["question"],
        "function": doc["function"],
    }
    write_list_of_dicts_to_file(INTERMEDIATE_FILE, [output_json], appendMode=True)
    return output_json

def runner(args, engine="gpt"):
    """Main runner function to handle the processing of all entries."""
    OUTPUT_FILE_NAME = f"quality_gpt_judge.json"
    if args.ckpt:
        OUTPUT_FILE_NAME = args.ckpt
    OUTPUT_FILE = os.path.join(OUTPUT_DIRECTORY, OUTPUT_FILE_NAME)

    # Load input file
    with open(INPUT_FILE, "r") as f:
        INPUT_FILE_DOC = [json.loads(doc) for doc in f.readlines()][600:900] # number of entries to process

    if args.ckpt:
        # Checkpoint recovery logic
        with open(OUTPUT_FILE, "r") as f:
            max_row = 0
            last_row = None
            for idx, line in enumerate(f.readlines()):
                max_row = max(max_row, json.loads(line)["id"])
                last_row = json.loads(line)
            print("Recovered from checkpoint", args.ckpt)
            print("Max row", max_row)
            print("Last row", last_row["id"])

        # Filter entries to resume processing from the checkpoint
        INPUT_FILE_DOC = [doc for doc in INPUT_FILE_DOC if doc["id"] > max_row]

    final_result = []
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = []
        for doc in INPUT_FILE_DOC:
            futures.append(executor.submit(process_entry, doc, OUTPUT_FILE, OUTPUT_FILE_NAME))

        results = [future.result() for future in as_completed(futures)]

        for result in tqdm(results):
            if result:
                final_result.append(result)

        # Write the final results to the output file
        write_list_of_dicts_to_file(OUTPUT_FILE, final_result)

# Input and output directories
INPUT_FILE = f"./berkeley-function-call-leaderboard/data/BFCL_v3_live_multiple.json"
OUTPUT_DIRECTORY = f"score_output"
OUTPUT_FILE_NAME = f"quality_gpt_judge.json"
OUTPUT_FILE = os.path.join(OUTPUT_DIRECTORY, OUTPUT_FILE_NAME)
print(OUTPUT_FILE)
INTERMEDIATE_DIRECTORY = OUTPUT_FILE[:-5] + "_intermediate"

# Create directories if they don't exist
if not os.path.exists(INTERMEDIATE_DIRECTORY):
    os.makedirs(INTERMEDIATE_DIRECTORY)
if not os.path.exists(OUTPUT_DIRECTORY):
    os.makedirs(OUTPUT_DIRECTORY)

# Run the script
if __name__ == "__main__":
    runner(args, engine="gpt")