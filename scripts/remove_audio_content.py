import json
import os
import tempfile
from pathlib import Path

def load_file(file_path, sort_by_id=False):
    result = []
    with open(file_path) as f:
        file = f.readlines()
        for line in file:
            # print(line)
            result.append(json.loads(line))

    # if sort_by_id:
    #     result.sort(key=sort_key)
    return result

def write_list_of_dicts_to_file(filename, data, subdir=None):
    # if subdir:
    #     # Determine the general category subfolder based on the filename, if possible
    #     test_category = extract_test_category(filename)
    #     group_dir_name = get_general_category(test_category)
    #     subdir = os.path.join(subdir, group_dir_name)

    #     # Ensure the (possibly nested) subdirectory exists
    #     os.makedirs(subdir, exist_ok=True)

    #     # Construct the full path to the file
    #     filename = os.path.join(subdir, os.path.basename(filename))

    # Write the list of dictionaries to the file in JSON format
    with open(filename, "w", encoding="utf-8") as f:
        for i, entry in enumerate(data):
            # Go through each key-value pair in the dictionary to make sure the values are JSON serializable
            # entry = make_json_serializable(entry)
            json_str = json.dumps(entry, ensure_ascii=False)
            f.write(json_str)
            if i < len(data) - 1:
                f.write("\n")


def scrub_audio_content(obj):
    """Recursively replace values of any `audio_content` keys in a JSON-like object."""
    if isinstance(obj, dict):
        return {
            key: ("audio_content removed for readability" if key == "audio_content" else scrub_audio_content(value))
            for key, value in obj.items()
        }
    if isinstance(obj, list):
        return [scrub_audio_content(item) for item in obj]
    return obj


def process_jsonl_file(path: Path):
    """Read a JSON Lines file, scrub each object, and overwrite the file in-place."""
    # Create a temporary file in the same directory to avoid partially-written files on crash
    data = load_file(path)
    data = scrub_audio_content(data)
    write_list_of_dicts_to_file(path, data)



def main():
    root = Path("/Users/huanzhi.mao/repo/gorilla/berkeley-function-call-leaderboard/result")
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            if filename.lower().endswith((".json", ".jsonl")):
                file_path = Path(dirpath) / filename
                print(f"Processing {file_path}...")
                process_jsonl_file(file_path)


if __name__ == "__main__":
    main()
