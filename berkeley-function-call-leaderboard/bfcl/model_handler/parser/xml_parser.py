import xml.etree.ElementTree as ET
import ast
import json

def parse_verbose_xml_function_call(input_str):
    root = ET.fromstring(input_str)
    results = []

    for func in root.findall('function'):
        func_name = func.attrib['name']
        param_dict = {}

        params_container = func.find('params')
        if params_container is not None:
            for param in params_container.findall('param'):
                name = param.attrib.get('name')
                raw_value = param.attrib.get('value', '')

                try:
                    parsed_value = ast.literal_eval(raw_value)
                except (ValueError, SyntaxError):
                    parsed_value = raw_value.strip()

                param_dict[name] = parsed_value

        results.append({func_name: param_dict})
    return results

def parse_concise_xml_function_call(input_str):
    root = ET.fromstring(input_str)
    results = []

    for func in root.findall('function'):
        func_name = func.attrib['name']
        param_dict = {}

        for param in func.findall('param'):
            name = param.attrib['name']
            raw_value = param.text

            # Handle string, int, float and empty string cases robustly
            try:
                parsed_value = ast.literal_eval(raw_value)
            except (ValueError, SyntaxError):
                parsed_value = raw_value.strip() if raw_value else ""

            param_dict[name] = parsed_value

        results.append({func_name: param_dict})

    return results
