import json
import os
import re

def load_file(file_path):
    result = []
    # Open the file in read mode
    with open(file_path) as f:
        file = f.readlines()
        for line in file:
            # Parse each line as JSON and append it to the result list
            result.append(json.loads(line))
    return result

def write_list_of_dicts_to_file(filename, data, subdir=None):
    if subdir:
        # Ensure the subdirectory exists
        os.makedirs(subdir, exist_ok=True)
        # Construct the full path to the file
        filename = os.path.join(subdir, filename)
    # Write the list of dictionaries to the file in JSON format
    with open(filename, "w") as f:
        for i, entry in enumerate(data):
            json_str = json.dumps(entry)
            f.write(json_str)
            if i < len(data) - 1:
                f.write("\n")

def sort_json(input_file_path, output_file_name, sort_key="id"):
    data = load_file(input_file_path)
    def sort_key_fn(entry):
        value = entry[sort_key]
        if isinstance(value, str):
            # If the value is a string, extract numbers and sort based on them
            numbers = re.findall(r'\d+', value)
            return list(map(int, numbers))  # Convert numbers to integers for sorting
        elif isinstance(value, int):
            # If the value is already an integer, return it directly
            return value
        else:
            # If it's neither string nor integer, return a large number to push it to the end
            return float('inf')
    # Sort data using the dynamic sort key function
    data.sort(key=sort_key_fn)
    write_list_of_dicts_to_file(output_file_name, data, subdir="")

sort_json("./score_output/quality_gpt_judge.json", "./score_output/quality_gpt_judge_sorted_score.json", "score")