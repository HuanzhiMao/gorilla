import json

from bfcl.model_handler.oss_model.base_oss_handler import OSSHandler
from overrides import override


class QwenFCHandler(OSSHandler):
    def __init__(self, model_name, temperature) -> None:
        super().__init__(model_name, temperature)

    @override
    def _format_prompt(self, messages, function):
        """
        "chat_template":        
        {%- if tools %}
            {{- '<|im_start|>system\n' }}
            {%- if messages[0]['role'] == 'system' %}
                {{- messages[0]['content'] }}
            {%- else %}
                {{- 'You are a helpful and harmless assistant. You are Qwen developed by Alibaba. You should think step-by-step.' }}
            {%- endif %}
            {{- "\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\nYou are provided with function signatures within <tools></tools> XML tags:\n<tools>" }}
            {%- for tool in tools %}
                {{- "\n" }}
                {{- tool | tojson }}
            {%- endfor %}
            {{- "\n</tools>\n\nFor each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n{\"name\": <function-name>, \"arguments\": <args-json-object>}\n</tool_call><|im_end|>\n" }}
        {%- else %}
            {%- if messages[0]['role'] == 'system' %}
                {{- '<|im_start|>system\n' + messages[0]['content'] + '<|im_end|>\n' }}
            {%- else %}
                {{- '<|im_start|>system\nYou are a helpful and harmless assistant. You are Qwen developed by Alibaba. You should think step-by-step.<|im_end|>\n' }}
            {%- endif %}
        {%- endif %}
        {%- for message in messages %}
            {%- if (message.role == "user") or (message.role == "system" and not loop.first) or (message.role == "assistant" and not message.tool_calls) %}
                {{- '<|im_start|>' + message.role + '\n' + message.content + '<|im_end|>' + '\n' }}
            {%- elif message.role == "assistant" %}
                {{- '<|im_start|>' + message.role }}
                {%- if message.content %}
                    {{- '\n' + message.content }}
                {%- endif %}
                {%- for tool_call in message.tool_calls %}
                    {%- if tool_call.function is defined %}
                        {%- set tool_call = tool_call.function %}
                    {%- endif %}
                    {{- '\n<tool_call>\n{"name": "' }}
                    {{- tool_call.name }}
                    {{- '", "arguments": ' }}
                    {{- tool_call.arguments | tojson }}
                    {{- '}\n</tool_call>' }}
                {%- endfor %}
                {{- '<|im_end|>\n' }}
            {%- elif message.role == "tool" %}
                {%- if (loop.index0 == 0) or (messages[loop.index0 - 1].role != "tool") %}
                    {{- '<|im_start|>user' }}
                {%- endif %}
                {{- '\n<tool_response>\n' }}
                {{- message.content }}
                {{- '\n</tool_response>' }}
                {%- if loop.last or (messages[loop.index0 + 1].role != "tool") %}
                    {{- '<|im_end|>\n' }}
                {%- endif %}
            {%- endif %}
        {%- endfor %}
        {%- if add_generation_prompt %}
            {{- '<|im_start|>assistant\n' }}
        {%- endif %}

        """
        formatted_prompt = ""
        
        if len(function) > 0:
            formatted_prompt += f"<|im_start|>system\nYou are a helpful and harmless assistant. You are Qwen developed by Alibaba. You should think step-by-step.\n\n# Tools\n\nYou may call one or more functions to assist with the user query.\n\nYou are provided with function signatures within <tools></tools> XML tags:\n<tools>"
            for tool in function:
                formatted_prompt += f"\n{json.dumps(tool, indent=4)}\n"
            formatted_prompt += "\n</tools>\n\nFor each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n{\"name\": <function-name>, \"arguments\": <args-json-object>}\n</tool_call><|im_end|>\n"
        else:
            formatted_prompt += f"<|im_start|>system\nYou are a helpful and harmless assistant. You are Qwen developed by Alibaba. You should think step-by-step.<|im_end|>\n"

        for idx, message in enumerate(messages):
            role = message["role"]
            content = message["content"]
            tool_calls = message.get("tool_calls", [])  # tool calls is only present for assistant messages

            if role == "user" or (role == "system" and idx != 0) or (role == "assistant" and not tool_calls):
                formatted_prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
            elif role == "assistant":
                formatted_prompt += f"<|im_start|>{role}"
                if content:
                    formatted_prompt += f"\n{content}"
                for tool_call in tool_calls:
                    if "function" in tool_call:
                        tool_call = tool_call["function"]
                    tool_name = tool_call.get("name", "")
                    arguments = tool_call.get("arguments", {})
                    formatted_prompt += (
                        f"\n<tool_call>\n{{\"name\": \"{tool_name}\", \"arguments\": {json.dumps(arguments)}}}\n</tool_call>"
                    )
                formatted_prompt += "<|im_end|>\n"
            elif role == "tool":
                if idx == 0 or messages[idx - 1]["role"] != "tool":
                    formatted_prompt += "<|im_start|>user"
                formatted_prompt += f"\n<tool_response>\n{content}\n</tool_response>"
                if idx == len(messages) - 1 or messages[idx + 1]["role"] != "tool":
                    formatted_prompt += "<|im_end|>\n"

        formatted_prompt += "<|im_start|>assistant\n"

        return formatted_prompt
