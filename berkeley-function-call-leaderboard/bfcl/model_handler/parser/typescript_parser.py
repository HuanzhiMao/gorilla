from tree_sitter import Language, Parser
import tree_sitter_javascript
import json
import ast
JS_LANGUAGE = Language(tree_sitter_javascript.language(), "javascript")

parser = Parser()
parser.set_language(JS_LANGUAGE)


def parse_typescript_function_call(source_code):

    def get_text(node):
        """Returns the text represented by the node."""
        return source_code[node.start_byte : node.end_byte]
    
    def process_call_expression(call_node):
        function_name = None
        arguments = {}
        for child in call_node.children:
            if child.type in ["identifier", "member_expression"]:
                function_name = get_text(child)
            if child.type == "arguments":
                arguments_node = child.children[1]
                for arg_child in arguments_node.children:
                    if arg_child.type == "pair":
                        for pair_child in arg_child.children:
                            if pair_child.type == "property_identifier":
                                arg_name = get_text(pair_child).strip()
                            if pair_child.type not in [":", "property_identifier"]:
                                arg_value = json.loads(get_text(pair_child).strip())
                        if arg_name in arguments:
                            raise Exception(
                                "Error: Multiple arguments with the same name are not supported."
                            )
                        arguments[arg_name] = arg_value
        return {function_name: arguments}

    tree = parser.parse(bytes(source_code, "utf8"))
    root_node = tree.root_node
    sexp_result = root_node.sexp()
    if "ERROR" in sexp_result:
        raise Exception("Error js parsing the source code.")
    
    calls_node = root_node.children[0].children[0]
    
    function_calls = []
    if calls_node.type == "array":
        for child in calls_node.children:
            if child.type == "call_expression":
                function_calls.append(process_call_expression(child))
    else:
        if calls_node.type == "call_expression":
            function_calls.append(process_call_expression(calls_node))
    
    return function_calls