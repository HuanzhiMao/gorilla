import os

from bfcl.model_handler.api_inference.openai import OpenAIHandler
from bfcl.model_handler.model_style import ModelStyle
from openai import OpenAI
from overrides import override


class QwenStreamAPIHandler(OpenAIHandler):
    def __init__(self, model_name, temperature) -> None:
        super().__init__(model_name, temperature)
        self.model_style = ModelStyle.OpenAI
        self.client = OpenAI(
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=os.getenv("QWEN_API_KEY"),
        )

    #### FC methods ####

    @override
    def _query_FC(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        tools = inference_data["tools"]
        inference_data["inference_input_log"] = {"message": repr(message), "tools": tools}

        return self.generate_with_backoff(
            messages=inference_data["message"],
            model=self.model_name.replace("-FC", ""),
            tools=tools,
            parallel_tool_calls=True,
            extra_body={"enable_thinking": True},
            stream=True,
            stream_options={
                "include_usage": True
            },  # retrieving token usage for stream response
        )

    @override
    def _parse_query_response_FC(self, api_response: any) -> dict:

        reasoning_content = ""
        answer_content = ""
        tool_info = []
        for chunk in api_response:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                reasoning_content += delta.reasoning_content

            if hasattr(delta, "content") and delta.content:
                answer_content += delta.content
                
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tool_call in delta.tool_calls:
                    # Index for parallel tool calls
                    index = tool_call.index
                    
                    # Dynamically extend the tool info storage list
                    while len(tool_info) <= index:
                        tool_info.append({})
                    
                    if tool_call.id:
                        tool_info[index]['id'] = tool_info[index].get('id', '') + tool_call.id
                    if tool_call.function and tool_call.function.name:
                        tool_info[index]['name'] = tool_info[index].get('name', '') + tool_call.function.name
                    if tool_call.function and tool_call.function.arguments:
                        tool_info[index]['arguments'] = tool_info[index].get('arguments', '') + tool_call.function.arguments

        tool_call_ids = []
        for item in tool_info:
            tool_call_ids.append(item["id"])
            
        if len(tool_info) > 0:
            

            model_response = [{item["name"]: item["arguments"]} for item in tool_info]
            model_response_message_for_chat_history = {
                "role": "assistant",
                "content": None,
                "tool_calls": tool_info,
            }
        else:
            model_response = answer_content
            model_response_message_for_chat_history = {
                "role": "assistant",
                "content": answer_content,
            }
        
        response_data = {
            "model_responses": model_response,
            "model_responses_message_for_chat_history": model_response_message_for_chat_history,
            "reasoning_content": reasoning_content,
            "tool_call_ids": tool_call_ids,
            # chunk is the last chunk of the stream response
            "input_token": chunk.usage.prompt_tokens,
            "output_token": chunk.usage.completion_tokens,
        }
        import json
        print(json.dumps(response_data, indent=4, ensure_ascii=False))
        return response_data


    #### Prompting methods ####


    @override
    def _query_prompting(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        inference_data["inference_input_log"] = {"message": repr(message)}

        return self.generate_with_backoff(
            messages=inference_data["message"],
            model=self.model_name.replace,
            extra_body={"enable_thinking": True},
            stream=True,
            stream_options={
                "include_usage": True
            },  # retrieving token usage for stream response
        )

    @override
    def _parse_query_response_prompting(self, api_response: any) -> dict:

        reasoning_content = ""
        answer_content = ""
        for chunk in api_response:
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                reasoning_content += delta.reasoning_content

            if hasattr(delta, "content") and delta.content:
                answer_content += delta.content

        response_data = {
            "model_responses": answer_content,
            "model_responses_message_for_chat_history": {
                "role": "assistant",
                "content": answer_content,
            },
            "reasoning_content": reasoning_content,
            # chunk is the last chunk of the stream response
            "input_token": chunk.usage.prompt_tokens,
            "output_token": chunk.usage.completion_tokens,
        }

        return response_data


