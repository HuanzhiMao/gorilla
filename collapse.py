import json

def collapse_json_objects(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    
    # To store individual JSON objects
    objects = []
    depth = 0
    obj_start = 0
    for i, char in enumerate(content):
        if char == '{':
            if depth == 0:
                obj_start = i
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                obj = content[obj_start:i+1]
                objects.append(obj)
    
    # Open the file to write newline-delimited JSON
    with open(file_path, 'w') as out_file:
        for obj in objects:
            try:
                # Try loading each individual object
                json_obj = json.loads(obj)
                # Write as compact JSON without spaces
                compact_json = json.dumps(json_obj, separators=(',', ':'))
                out_file.write(compact_json + '\n')
            except json.JSONDecodeError:
                # If there's an error, write the raw object without collapsing it
                print(f"Failed to decode JSON object, writing uncollapsed: {obj}")
                out_file.write(obj + '\n')

# Use the function with the file path
collapse_json_objects('/Users/vishnusuresh/Desktop/gorilla/gorilla-vishnu/correction.json')
