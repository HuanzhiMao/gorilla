import json
from bfcl.model_handler.utils import default_decode_ast_prompting
from bfcl.model_handler.api_inference.mistral import MistralHandler
from bfcl.eval_checker.eval_runner import get_handler
from bfcl.utils import get_all_prompt_variation_configs
from openai import OpenAI

client = OpenAI()

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What is the capital of France?"}
    ]
)

print(response.choices[0].message.content)


# model_name = "meta-llama_Llama-3.1-70B-Instruct"
# return_format = "json"
# function_doc_format = "python"
# has_tool_tag = "False"
# # test_category = "live_simple"
# # test_categories = ["simple", "multiple", "parallel", "parallel_multiple", "live_simple", "live_multiple", "live_parallel", "live_parallel_multiple"]
# test_categories = ["simple"]

# for test_category in test_categories:
#     filename = f"BFCL_v3_{test_category}_score_function_doc_format_{function_doc_format}_has_available_tools_tag_False_has_tool_call_tag_{has_tool_tag}_prompt_format_plaintext_prompt_style_classic_return_format_{return_format}.json"
#     filepath = f"./score/{model_name}/prompt_variation/{filename}"
#     print(filename)
#     with open(filepath, 'r') as f:
#         metadata = json.loads(f.readline())
#     print(test_category, metadata["accuracy"], metadata["total_count"])



# s = "<functions>\n<function name=\"calculate_distance\">\n<param name=\"body1\" type=\"string\">Mars</param>\n<param name=\"body2\" type=\"string\">Venus</param>\n<param name=\"unit\" type=\"string\">miles</param>\n</function>\n</functions>\n\n<functions>\n<function name=\"calculate_distance\">\n<param name=\"body1\" type=\"string\">Mars</param>\n<param name=\"body2\" type=\"string\">Jupiter</param>\n<param name=\"unit\" type=\"string\">miles</param>\n</function>\n</functions>"
# s = "```json\n[{\"function\":\"convert_currency\",\"parameters\":{\"base_currency\":\"JPY\",\"target_currency\":\"USD\",\"amount\":20000}}]\n```"

# s = "<functions>\n  <function name=\"entropy_change.calculate\">\n    <params>\n      <param name=\"substance\" value=\"A\" type=\"string\"/>\n      <param name=\"mass\" value=\"2\" type=\"integer\"/>\n      <param name=\"initial_temperature\" value=\"25\" type=\"integer\"/>\n      <param name=\"final_temperature\" value=\"75\" type=\"integer\"/>\n      <param name=\"pressure\" value=\"1\" type=\"integer\"/>\n    </params>\n  </function>\n  <function name=\"entropy_change.calculate\">\n    <params>\n      <param name=\"substance\" value=\"A\" type=\"string\"/>\n      <param name=\"mass\" value=\"2\" type=\"integer\"/>\n      <param name=\"initial_temperature\" value=\"10\" type=\"integer\"/>\n      <param name=\"final_temperature\" value=\"50\" type=\"integer\"/>\n      <param name=\"pressure\" value=\"1\" type=\"integer\"/>\n    </params>\n  </function>\n</functions>"

# s = "<functions><function name=\"entropy_change.calculate\"><params><param name=\"substance\" value=\"A\" type=\"string\"/><param name=\"mass\" value=\"2\" type=\"integer\"/><param name=\"initial_temperature\" value=\"25\" type=\"integer\"/><param name=\"final_temperature\" value=\"75\" type=\"integer\"/><param name=\"pressure\" value=\"1\" type=\"integer\"/></params></function><function name=\"entropy_change.calculate\">\n    <params>\n      <param name=\"substance\" value=\"A\" type=\"string\"/>\n      <param name=\"mass\" value=\"2\" type=\"integer\"/>\n      <param name=\"initial_temperature\" value=\"10\" type=\"integer\"/>\n      <param name=\"final_temperature\" value=\"50\" type=\"integer\"/>\n      <param name=\"pressure\" value=\"1\" type=\"integer\"/>\n    </params>\n  </function>\n</functions>"

# handler = get_handler("microsoft/phi-4")
# decoded = handler.decode_ast(s, "concise_xml")
# print(decoded)

# print(get_all_prompt_variation_configs())
'''

<functions>
    <function name=\"calculate_distance\">
        <param name=\"body1\" type=\"string\">Mars</param>
        <param name=\"body2\" type=\"string\">Venus</param>
        <param name=\"unit\" type=\"string\">miles</param>
    </function>
</functions>
<functions>
    <function name=\"calculate_distance\">
        <param name=\"body1\" type=\"string\">Mars</param>
        <param name=\"body2\" type=\"string\">Jupiter</param>
        <param name=\"unit\" type=\"string\">miles</param>
    </function>
</functions>

'''