from bfcl.model_handler.oss_model.base_oss_handler import OSSHandler
from bfcl.model_handler.utils import func_doc_language_specific_pre_processing, convert_system_prompt_into_user_prompt, combine_consecutive_user_prompts
from bfcl.model_handler.constant import DEFAULT_SYSTEM_PROMPT
import json

class MistralFCHandler(OSSHandler):
    def __init__(self, model_name, temperature) -> None:
        super().__init__(model_name, temperature)
    
    @staticmethod
    def _construct_func_doc(functions):
        """
        {{- "[AVAILABLE_TOOLS] [" }}
        {%- for tool in tools %}
            {%- set tool = tool.function %}
            {{- '{"type": "function", "function": {' }}
            {%- for key, val in tool.items() if key != "return" %}
                {%- if val is string %}
                    {{- '"' + key + '": "' + val + '"' }}
                {%- else %}
                    {{- '"' + key + '": ' + val|tojson }}
                {%- endif %}
                {%- if not loop.last %}
                    {{- ", " }}
                {%- endif %}
            {%- endfor %}
            {{- "}}" }}
            {%- if not loop.last %}
                {{- ", " }}
            {%- else %}
                {{- "]" }}
            {%- endif %}
        {%- endfor %}
        {{- "[/AVAILABLE_TOOLS]" }}
        """
        func_docs = []
        for tool in functions:
            func_doc = '{"type": "function", "function": {'
            func_doc += ', '.join(
                f'"{key}": "{val}"' if isinstance(val, str) else f'"{key}": {json.dumps(val)}' 
                for key, val in tool.items() if key != "return"
            )
            func_doc += "}}"
            func_docs.append(func_doc)

        result_str = "[AVAILABLE_TOOLS] [" + ', '.join(func_docs) + "][/AVAILABLE_TOOLS]"
        return result_str

    def _format_prompt(self, messages, function):
        """
        "bos_token": "<s>"
        "eos_token": "</s>"

        {%- if messages[0]["role"] == "system" %}
            {%- set system_message = messages[0]["content"] %}
            {%- set loop_messages = messages[1:] %}
        {%- else %}
            {%- set loop_messages = messages %}
        {%- endif %}
        {%- if not tools is defined %}
            {%- set tools = none %}
        {%- endif %}
        {%- set user_messages = loop_messages | selectattr("role", "equalto", "user") | list %}

        {#- This block checks for alternating user/assistant messages, skipping tool calling messages #}
        {%- set ns = namespace() %}
        {%- set ns.index = 0 %}
        {%- for message in loop_messages %}
            {%- if not (message.role == "tool" or message.role == "tool_results" or (message.tool_calls is defined and message.tool_calls is not none)) %}
                {%- if (message["role"] == "user") != (ns.index % 2 == 0) %}
                    {{- raise_exception("After the optional system message, conversation roles must alternate user/assistant/user/assistant/...") }}
                {%- endif %}
                {%- set ns.index = ns.index + 1 %}
            {%- endif %}
        {%- endfor %}

        {{- bos_token }}
        {%- for message in loop_messages %}
            {%- if message["role"] == "user" %}
                {%- if tools is not none and (message == user_messages[-1]) %}
                    {{- "[AVAILABLE_TOOLS] [" }}
                    {%- for tool in tools %}
                        {%- set tool = tool.function %}
                        {{- '{"type": "function", "function": {' }}
                        {%- for key, val in tool.items() if key != "return" %}
                            {%- if val is string %}
                                {{- '"' + key + '": "' + val + '"' }}
                            {%- else %}
                                {{- '"' + key + '": ' + val|tojson }}
                            {%- endif %}
                            {%- if not loop.last %}
                                {{- ", " }}
                            {%- endif %}
                        {%- endfor %}
                        {{- "}}" }}
                        {%- if not loop.last %}
                            {{- ", " }}
                        {%- else %}
                            {{- "]" }}
                        {%- endif %}
                    {%- endfor %}
                    {{- "[/AVAILABLE_TOOLS]" }}
                    {%- endif %}
                {%- if loop.last and system_message is defined %}
                    {{- "[INST] " + system_message + "\n\n" + message["content"] + "[/INST]" }}
                {%- else %}
                    {{- "[INST] " + message["content"] + "[/INST]" }}
                {%- endif %}
            {%- elif message.tool_calls is defined and message.tool_calls is not none %}
                {{- "[TOOL_CALLS] [" }}
                {%- for tool_call in message.tool_calls %}
                    {%- set out = tool_call.function|tojson %}
                    {{- out[:-1] }}
                    {%- if not tool_call.id is defined or tool_call.id|length != 9 %}
                        {{- raise_exception("Tool call IDs should be alphanumeric strings with length 9!") }}
                    {%- endif %}
                    {{- ', "id": "' + tool_call.id + '"}' }}
                    {%- if not loop.last %}
                        {{- ", " }}
                    {%- else %}
                        {{- "]" + eos_token }}
                    {%- endif %}
                {%- endfor %}
            {%- elif message["role"] == "assistant" %}
                {{- " " + message["content"]|trim + eos_token}}
            {%- elif message["role"] == "tool_results" or message["role"] == "tool" %}
                {%- if message.content is defined and message.content.content is defined %}
                    {%- set content = message.content.content %}
                {%- else %}
                    {%- set content = message.content %}
                {%- endif %}
                {{- '[TOOL_RESULTS] {"content": ' + content|string + ", " }}
                {%- if not message.tool_call_id is defined or message.tool_call_id|length != 9 %}
                    {{- raise_exception("Tool call IDs should be alphanumeric strings with length 9!") }}
                {%- endif %}
                {{- '"call_id": "' + message.tool_call_id + '"}[/TOOL_RESULTS]' }}
            {%- else %}
                {{- raise_exception("Only user and assistant roles are supported, with the exception of an initial optional system message!") }}
            {%- endif %}
        {%- endfor %}
        """
        bos_token="<s>"
        eos_token="</s>"

        formatted_prompt = bos_token

        user_messages = [msg for msg in messages if msg["role"] == "user"]

        for message in messages:
            if message["role"] == "user":
                if function and message == user_messages[-1]:  # If tools are defined and this is the last user message
                    formatted_prompt += self._construct_func_doc(function)

                formatted_prompt += f'[INST] {message["content"]}[/INST]'
            
            elif message.get("tool_calls") is not None:
                tool_calls_parts = []
                for tool_call in message["tool_calls"]:
                    tool_call_json = tool_call["function"]
                    if "id" not in tool_call or len(tool_call["id"]) != 9:
                        raise Exception("Tool call IDs should be alphanumeric strings with length 9!")
                    tool_call_json["id"] = tool_call["id"]
                    tool_calls_parts.append(tool_call_json)
                formatted_prompt += f'[TOOL_CALLS] {tool_calls_parts}{eos_token}'

            elif message["role"] == "assistant":
                formatted_prompt += f" {message['content'].strip()}{eos_token}"

            elif message["role"] == "tool":
                formatted_prompt += '[TOOL_RESULTS] {"content": ' + message["content"] + ", " + '"call_id": "' + message["tool_call_id"] + '"}[/TOOL_RESULTS]'
            
            else:
                raise Exception("Only user and assistant roles are supported, with the exception of an initial optional system message!")

        return formatted_prompt


    def _pre_query_processing_prompting(self, test_entry: dict) -> dict:
        functions: list = test_entry["function"]
        test_category: str = test_entry["id"].rsplit("_", 1)[0]

        functions = func_doc_language_specific_pre_processing(functions, test_category)
        # We don't add system prompt 
        for round_idx in range(len(test_entry["question"])):
            test_entry["question"][round_idx] = convert_system_prompt_into_user_prompt(
                test_entry["question"][round_idx]
            )
            test_entry["question"][round_idx] = combine_consecutive_user_prompts(
                test_entry["question"][round_idx]
            )
        return {"message": [], "function": functions}
    
    def _add_execution_results_prompting(
        self, inference_data: dict, execution_results: list[str], model_response_data: dict
    ) -> dict:
        for execution_result, tool_call_id in zip(
            execution_results, model_response_data["tool_call_ids"]
        ):
            inference_data["message"].append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": execution_result,
                }
            )

        return inference_data
