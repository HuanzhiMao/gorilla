import json
from typing import Dict, List, Any

OUTPUT_FORMAT_MAPPING = {
    "python": "```python\n[func_name1(params_name1=params_value1, params_name2=params_value2...), func_name2(params)]\n```",
    "json": "```json\n[{\"function\":\"func_name1\",\"parameters\":{\"param1\":\"value1\",\"param2\":\"value2\"}},{\"function\":\"func_name2\",\"parameters\":{\"param\":\"value\"}}]\n```",
    "typescript": "```typescript\nconst calls:[{function:string;parameters:Record<string,any>}] = [{function:\"func_name1\",parameters:{param1:\"value1\",param2:\"value2\"}},{function:\"func_name2\",parameters:{param:\"value\"}}];\n```",
    "verbose_xml": "```xml\n<functions><function name=\"func_name1\"><param name=\"param1\">value1</param><param name=\"param2\">value2</param></function><function name=\"func_name2\"><param name=\"param\">value</param></function></functions>\n```",
    "concise_xml": "```xml\n<functions><func_name1 param1=\"value1\" param2=\"value2\" /><func_name2 param=\"value\" /></functions>\n```"
}

PROMPT_STYLE_MAPPING = {
    "classic": {
        "persona": "You are an expert in composing functions.",
        "task": "You are given a question and a set of possible functions. Based on the question, you will need to make one or more function/tool calls to achieve the purpose. If none of the functions can be used, point it out. If the given question lacks the parameters required by the function, also point it out.",
        "tool_call_no_tag": "You should only return the function calls in your response.\n\nIf you decide to invoke any of the function(s), you MUST put it in the format of {output_format}.You SHOULD NOT include any other text in the response.",
        "tool_call_with_tag": "You should only return the function calls in the <TOOLCALL> section. If you decide to invoke any of the function(s), you MUST put it in the format of <TOOLCALL>{output_format}</TOOLCALL>. You SHOULD NOT include any other text in the response.",
        "multiturn": "At each turn, you should try your best to complete the tasks requested by the user within the current turn. Continue to output functions to call until you have fulfilled the user's request to the best of your ability. Once you have no more functions to call, the system will consider the current turn complete and proceed to the next turn or task.",
        "available_tools_no_tag": "Here is a list of functions in JSON format that you can invoke.\n{functions}\n",
        "available_tools_with_tag": "Here is a list of functions in JSON format that you can invoke.<AVAILABLE_TOOLS>{functions}</AVAILABLE_TOOLS>\n"
    },
    "experimental": {
        "persona": "You are an experienced developer.",
        "task": "You need to make function/tool calls to solve the question given. If none of the functions can be used or the given question lacks the parameters, return an empty list then explain.",
        "tool_call_no_tag": "If you decide to invoke any of the function(s), you MUST put it in the format of {output_format}. You SHOULD NOT include any other text in the response.",
        "tool_call_with_tag": "You should only return the function calls in the <TOOLCALL> section. If you decide to invoke any of the function(s), you MUST put it in the format of <TOOLCALL>{output_format}</TOOLCALL>.",
        "multiturn": "At each turn, you should try your best to complete the tasks requested by the user within the current turn. Continue to output functions to call until you have fulfilled the user's request to the best of your ability. Once you have no more functions to call, the system will consider the current turn complete and proceed to the next turn or task.",
        "available_tools_no_tag": "Functions:\n```json\n{functions}\n```",
        "available_tools_with_tag": "<AVAILABLE_TOOLS>{functions}</AVAILABLE_TOOLS>"
    }
}


def formulate_default_system_prompt(
    prompt_format: str = "plaintext",    # 'plaintext' | 'markdown'
    prompt_style: str = "classic",       # 'classic' | 'experimental'
    return_format: str = "python",       # 'python' | 'json' | 'typescript' | 'verbose_xml' | 'concise_xml'
    has_tool_call_tag: bool = False,
    functions: str = ""                  # stringified JSON for {functions} placeholder
) -> str:
    """
    Formulate the default system prompt based on the provided parameters.
    """
    default_prompt = ""

    if prompt_format == "plaintext":
        default_prompt = "{persona}{task}\n\n{tool_call}\n\n{multiturn}\n\n{available_tools}"
    elif prompt_format == "markdown":
        default_prompt = "{persona}\n\n## Task\n{task}\n\n## Tool Call Format\n{tool_call}\n\n## Multi-turn Behavior\n{multiturn}\n\n## Available Tools\n{available_tools}"

    tool_call_key = "tool_call_with_tag" if has_tool_call_tag else "tool_call_no_tag"
    available_tools_key = "available_tools_with_tag" if has_tool_call_tag else "available_tools_no_tag"
    
    default_prompt = default_prompt.format(
        persona=PROMPT_STYLE_MAPPING[prompt_style]["persona"],
        task=PROMPT_STYLE_MAPPING[prompt_style]["task"],
        tool_call=PROMPT_STYLE_MAPPING[prompt_style][tool_call_key].format(output_format=OUTPUT_FORMAT_MAPPING[return_format]),
        multiturn=PROMPT_STYLE_MAPPING[prompt_style]["multiturn"],
        available_tools=PROMPT_STYLE_MAPPING[prompt_style][available_tools_key].format(functions=functions)
    )

    return default_prompt


# def main():
#     """
#     Generate and print example prompts with different configurations.
#     """
#     # Sample functions for demonstration
#     sample_functions = [
#         {
#             "name": "get_weather",
#             "description": "Get the current weather in a given location",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "location": {
#                         "type": "string",
#                         "description": "The city and state, e.g. San Francisco, CA"
#                     },
#                     "unit": {
#                         "type": "string",
#                         "enum": ["celsius", "fahrenheit"],
#                         "description": "The temperature unit to use"
#                     }
#                 },
#                 "required": ["location"]
#             }
#         },
#         {
#             "name": "search_restaurants",
#             "description": "Search for restaurants in a given location",
#             "parameters": {
#                 "type": "object",
#                 "properties": {
#                     "location": {
#                         "type": "string",
#                         "description": "The city and state, e.g. San Francisco, CA"
#                     },
#                     "cuisine": {
#                         "type": "string",
#                         "description": "Type of cuisine, e.g. Italian, Chinese"
#                     },
#                     "price_range": {
#                         "type": "string",
#                         "enum": ["$", "$$", "$$$", "$$$$"],
#                         "description": "Price range from $ (cheap) to $$$$ (expensive)"
#                     }
#                 },
#                 "required": ["location"]
#             }
#         }
#     ]
    
#     # Convert functions to JSON string
#     functions_json = json.dumps(sample_functions, indent=2)
    
#     # Print header
#     print("=" * 80)
#     print("PROMPT GENERATOR EXAMPLES")
#     print("=" * 80)
    
#     # Example 1: Classic plaintext Python format without tags
#     print("\n\nEXAMPLE 1: Classic plaintext with Python format, no tags\n")
#     prompt1 = formulate_default_system_prompt(
#         prompt_format="plaintext",
#         prompt_style="classic",
#         return_format="python",
#         has_tool_call_tag=False,
#         functions=functions_json
#     )
#     print(prompt1)
#     print("\n" + "=" * 80)
    
#     # Example 2: Experimental markdown JSON format with tags
#     print("\n\nEXAMPLE 2: Experimental markdown with JSON format, with tags\n")
#     prompt2 = formulate_default_system_prompt(
#         prompt_format="markdown", 
#         prompt_style="experimental",
#         return_format="json",
#         has_tool_call_tag=True,
#         functions=functions_json
#     )
#     print(prompt2)
#     print("\n" + "=" * 80)
    
#     # Example 3: Classic plaintext TypeScript format
#     print("\n\nEXAMPLE 3: Classic plaintext with TypeScript format\n")
#     prompt3 = formulate_default_system_prompt(
#         prompt_format="plaintext",
#         prompt_style="classic", 
#         return_format="typescript",
#         has_tool_call_tag=False,
#         functions=functions_json
#     )
#     print(prompt3)
#     print("\n" + "=" * 80)
    
#     # Example 4: Expreimental plaintext with verbose XML format
#     print("\n\nEXAMPLE 4: Expreimental plaintext with verbose XML format\n")
#     prompt4 = formulate_default_system_prompt(
#         prompt_format="plaintext",
#         prompt_style="experimental",
#         return_format="verbose_xml",
#         has_tool_call_tag=False,
#         functions=functions_json
#     )
#     print(prompt4)
#     print("\n" + "=" * 80)
    
#     # Example 5: Classic markdown with concise XML format and tags
#     print("\n\nEXAMPLE 5: Classic markdown with concise XML format and tags\n")
#     prompt5 = formulate_default_system_prompt(
#         prompt_format="markdown",
#         prompt_style="classic",
#         return_format="concise_xml",
#         has_tool_call_tag=True,
#         functions=functions_json
#     )
#     print(prompt5)
#     print("\n" + "=" * 80)


# if __name__ == "__main__":
#     main()