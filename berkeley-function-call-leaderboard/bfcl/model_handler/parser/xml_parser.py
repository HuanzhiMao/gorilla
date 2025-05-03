import xml.etree.ElementTree as ET
import ast
import json

def parse_xml_function_call(source_code):
    root = ET.fromstring(source_code)

    func_tag_name = None
    if root.find('func_call') is not None:
        func_tag_name = 'func_call'
    elif root.find('function') is not None:
        func_tag_name = 'function'
    else:
        raise Exception(
            "Error: function tag name not supported."
        )

    result = []
    for func_call in root.findall(func_tag_name):
        func_name = func_call.get('name')
        arguments = {}
        if func_call.find('args') is not None:
            for arg in func_call.find('args').findall('arg'):
                arg_name = arg.get('name')
                if 'value' in arg.attrib:
                    arg_value = arg.get('value')
                else:
                    arg_value = arg.text.strip() if arg.text else ''
                try:
                    parsed_value = json.loads(arg_value)
                except (ValueError, SyntaxError):
                    parsed_value = arg_value
                if arg_name in arguments:
                    if not isinstance(arguments[arg_name], list):
                        arguments[arg_name] = [arguments[arg_name]]
                    arguments[arg_name].append(parsed_value)
                else:
                    arguments[arg_name] = parsed_value
        else:
            for arg in func_call.findall('arg'):
                arg_name = arg.get('name')
                if 'value' in arg.attrib:
                    arg_value = arg.get('value')
                else:
                    arg_value = arg.text.strip() if arg.text else ''
                try:
                    parsed_value = json.loads(arg_value)
                except (ValueError, SyntaxError):
                    parsed_value = arg_value
                if arg_name in arguments:
                    raise Exception(
                        "Error: Multiple arguments with the same name are not supported."
                    )
                else:
                    arguments[arg_name] = parsed_value

        result.append({func_name: arguments})
    return result