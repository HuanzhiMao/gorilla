import time,json
from model_handler.nvidia_handler import NvidiaHandler
from model_handler.utils import (
    convert_to_tool,
    convert_to_function_call,
    system_prompt_pre_processing,
    user_prompt_pre_processing_chat_model,
    func_doc_language_specific_pre_processing,
)
from model_handler.constant import (
    GORILLA_TO_OPENAPI,
)

class LlamaNvidiaHandler(NvidiaHandler):
    def __init__(self, model_name, temperature=0.001, top_p=1, max_tokens=1000) -> None:
        super().__init__(model_name, temperature, top_p, max_tokens)
    
    def inference(self, prompt, functions, test_category):
        if "FC" not in self.model_name:
            return super().inference(prompt,functions,test_category)
        else:
            functions = func_doc_language_specific_pre_processing(functions, test_category)

            message = prompt
            oai_tool = convert_to_tool(
                functions, GORILLA_TO_OPENAPI, self.model_style, test_category
            )
            start_time = time.time()
            if len(oai_tool) > 0:
                response = self.client.chat.completions.create(
                    messages=message,
                    model=self.model_name.replace("-FC", ""),
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                    tools=oai_tool,
                )
            else:
                response = self.client.chat.completions.create(
                    messages=message,
                    model=self.model_name.replace("-FC", ""),
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                )
            latency = time.time() - start_time
            try:
                result = [
                    {func_call.function.name: func_call.function.arguments}
                    for func_call in response.choices[0].message.tool_calls
                ]
            except:
                result = response.choices[0].message.content
            metadata = {}
            metadata["input_tokens"] = response.usage.prompt_tokens
            metadata["output_tokens"] = response.usage.completion_tokens
            metadata["latency"] = latency
        return result,metadata
    def decode_ast(self, result, language="Python"):
        if "FC" not in self.model_name:
            super().decode_ast(result, language)
        else:
            decoded_output = []
            for invoked_function in result:
                name = list(invoked_function.keys())[0]
                params = json.loads(invoked_function[name])
                decoded_output.append({name: params})
            return decoded_output

    def decode_execute(self, result, language="Python"):
        if "FC" not in self.model_name:
            super().decode_execute(result, language)
        else:
            function_call = convert_to_function_call(result)
            return function_call