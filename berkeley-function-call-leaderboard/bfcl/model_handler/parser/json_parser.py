import ast
import json

def parse_json_function_call(source_code):
    json_dict = json.loads(source_code)
    function_calls = []
    for function_call in json_dict:
        if isinstance(function_call, dict):
            function_name = function_call["function"]
            arguments = function_call["parameters"]
            function_calls.append({function_name: arguments})
    return function_calls