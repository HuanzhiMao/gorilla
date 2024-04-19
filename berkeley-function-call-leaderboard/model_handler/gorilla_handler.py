import json
import requests
import time,os

from model_handler.oss_handler import OSSHandler
from model_handler.utils import ast_parse, augment_prompt_by_languge, language_specific_pre_processing
from model_handler.model_style import ModelStyle

FN_CALL_DELIMITER = "<<function>>"


def strip_function_calls(content: str) -> list[str]:
    """
    Split the content by the function call delimiter and remove empty strings
    """
    return [element.strip() for element in content.split(FN_CALL_DELIMITER)[1:] if element.strip()]


class OpenfunctionsHandler(OSSHandler):

    def __init__(self, model_name, temperature=0.7, top_p=1, max_tokens=1000) -> None:
        if model_name == "gorilla-openfunctions-v2":
            # Hosted for free with ❤️ from UC Berkeley
            self.model_name = model_name
            self.temperature = temperature
            self.top_p = top_p
            self.max_tokens = max_tokens
        elif model_name == "gorilla-openfunctions-v2-local":
            # Self-hosted gorilla openfunctions 
            super().__init__(model_name, temperature, top_p, max_tokens)
            self.model_name = "gorilla-llm/gorilla-openfunctions-v2"
            self.temperature = 0.0
        self.model_style = ModelStyle.Gorilla

    def _get_gorilla_response(self, prompt, functions):
        """
            Get Openfunctions Response from Gorilla hosted endpoints.
        """
        requestData = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "functions": functions,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
        }
        url = "https://luigi.millennium.berkeley.edu:443/v1/chat/completions"
        start = time.time()
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": "EMPTY", 
            },
            data=json.dumps(requestData),
        )
        latency = time.time() - start
        jsonResponse = response.json()
        metadata = {}
        metadata["input_tokens"] = jsonResponse["usage"]["prompt_tokens"]
        metadata["output_tokens"] = jsonResponse["usage"]["completion_tokens"]
        metadata["latency"] = latency
        directCode = jsonResponse["choices"][0]["message"]["content"]
        return directCode, metadata
    
    def _format_prompt(user_query: str, functions: list, test_category: str) -> str:
        """
        Generates a conversation prompt based on the user's query and a list of functions.

        Parameters:
        - user_query (str): The user's query.
        - functions (list): A list of functions to include in the prompt.
        - test_category (str): selected test category


        Returns:
        - str: The formatted conversation prompt.
        """
        system = "You are an AI programming assistant, utilizing the Gorilla LLM model, developed by Gorilla LLM, and you only answer questions related to computer science. For politically sensitive questions, security and privacy issues, and other non-computer science questions, you will refuse to answer."
        if len(functions) == 0:
            return f"{system}\n### Instruction: <<question>> {user_query}\n### Response: "
        functions_string = json.dumps(functions)
        return f"{system}\n### Instruction: <<function>>{functions_string}\n<<question>>{user_query}\n### Response: "
    
    def _inference_from_huggingface(
        self, question_file, test_category, num_gpus, format_prompt_func=_format_prompt
    ):
            return super().inference(
                question_file, test_category, num_gpus, format_prompt_func
            )
    
    def _inference_from_endpoint(self, prompt, functions, test_category):
            prompt = augment_prompt_by_languge(prompt, test_category)
            functions = language_specific_pre_processing(functions, test_category, False)
            if type(functions) is not list:
                functions = [functions]
            try:
                result, metadata = self._get_gorilla_response(prompt, functions)
            except KeyboardInterrupt:
                raise KeyboardInterrupt
            except:
                result = "Error"
                metadata = {"input_tokens": 0, "output_tokens": 0, "latency": 0}
            return result, metadata

    def decode_ast(self, result, language="Python"):
        if self.model_name == "gorilla-llm/gorilla-openfunctions-v2":
            result = strip_function_calls(result)
            func = "[" + ",".join(result) + "]"
        else:
            func = "[" + result + "]"
        decoded_output = ast_parse(func, language)
        return decoded_output

    def decode_execute(self, result):
        if self.model_name == "gorilla-llm/gorilla-openfunctions-v2":
            result = strip_function_calls(result)
            func = "[" + ",".join(result) + "]"
        else:
            func = "[" + result + "]"
        decoded_output = ast_parse(func)
        execution_list = []
        for function_call in decoded_output:
            for key, value in function_call.items():
                execution_list.append(
                    f"{key}({','.join([f'{k}={repr(v)}' for k, v in value.items()])})"
                )
        return execution_list
    
    def inference(self, *args):
        if self.model_name == "gorilla-openfunctions-v2":
            return self._inference_from_endpoint(*args)
        elif self.model_name == "gorilla-llm/gorilla-openfunctions-v2":
            return self._inference_from_huggingface(*args)
    
    def write(self, result, file_to_open):
        if self.model_name == "gorilla-openfunctions-v2":
            super().write(result, file_to_open)
        elif self.model_name == "gorilla-llm/gorilla-openfunctions-v2":
            if not os.path.exists("./result"):
                os.mkdir("./result")
            if not os.path.exists("./result/" + "gorilla-openfunctions-v2-local"):
                os.mkdir("./result/" +  "gorilla-openfunctions-v2-local")
            with open(
                "./result/"
                + "gorilla-openfunctions-v2-local"
                + "/"
                + file_to_open,
                "a+",
            ) as f:
                f.write(json.dumps(result) + "\n")