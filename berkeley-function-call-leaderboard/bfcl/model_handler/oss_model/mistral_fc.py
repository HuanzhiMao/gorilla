from bfcl.model_handler.oss_model.base_oss_handler import OSSHandler


class MistralFCHandler(OSSHandler):
    def __init__(self, model_name, temperature) -> None:
        super().__init__(model_name, temperature)

    def _format_prompt(self, messages, function):
        """
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
        bos_token="<|begin_of_text|>", eos_token="<|end_of_text|>"
        # Step 1: Handle system message
        if messages[0]["role"] == "system":
            system_message = messages[0]["content"]
            loop_messages = messages[1:]
        else:
            loop_messages = messages

        # Step 2: Initialize the namespace index for role alternation check
        ns_index = 0

        # Step 3: Role alternation check and exceptions
        for message in loop_messages:
            if not (message["role"] == "tool" or message["role"] == "tool_results" or (message.get("tool_calls") is not None)):
                if (message["role"] == "user") != (ns_index % 2 == 0):
                    raise Exception("After the optional system message, conversation roles must alternate user/assistant/user/assistant/...")
                ns_index += 1

        # Step 4: Start building the formatted template with beginning of the sequence token
        formatted_chat = bos_token

        # Step 5: Loop through messages and build the formatted output
        user_messages = [msg for msg in loop_messages if msg["role"] == "user"]

        for message in loop_messages:
            if message["role"] == "user":
                if tools and message == user_messages[-1]:  # If tools are defined and this is the last user message
                    tool_parts = []
                    for tool in tools:
                        tool_function = tool["function"]
                        tool_call = ', '.join(
                            f'"{key}": "{val}"' if isinstance(val, str) else f'"{key}": {val}' 
                            for key, val in tool_function.items() if key != "return"
                        )
                        tool_parts.append(f'{{"type": "function", "function": {{{tool_call}}}}}')
                    formatted_chat += f"[AVAILABLE_TOOLS] [{', '.join(tool_parts)}][/AVAILABLE_TOOLS]"
                if message == loop_messages[-1] and "system_message" in locals():
                    formatted_chat += f'[INST] {system_message}\n\n{message["content"]}[/INST]'
                else:
                    formatted_chat += f'[INST] {message["content"]}[/INST]'
            
            elif message.get("tool_calls") is not None:
                tool_calls_parts = []
                for tool_call in message["tool_calls"]:
                    tool_call_json = tool_call["function"]
                    if "id" not in tool_call or len(tool_call["id"]) != 9:
                        raise Exception("Tool call IDs should be alphanumeric strings with length 9!")
                    tool_call_json["id"] = tool_call["id"]
                    tool_calls_parts.append(tool_call_json)
                formatted_chat += f'[TOOL_CALLS] {tool_calls_parts}{eos_token}'

            elif message["role"] == "assistant":
                formatted_chat += f" {message['content'].strip()}{eos_token}"

            elif message["role"] == "tool_results" or message["role"] == "tool":
                content = message["content"].get("content", message["content"]) if message.get("content") else ""
                if "tool_call_id" not in message or len(message["tool_call_id"]) != 9:
                    raise Exception("Tool call IDs should be alphanumeric strings with length 9!")
                formatted_chat += f'[TOOL_RESULTS] {{"content": "{content}", "call_id": "{message["tool_call_id"]}"}}[/TOOL_RESULTS]'
            
            else:
                raise Exception("Only user and assistant roles are supported, with the exception of an initial optional system message!")

        return formatted_chat

