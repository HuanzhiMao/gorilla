import os

from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from bfcl_eval.constants.enums import ModelStyle
from openai import OpenAI


class MiningHandler(OpenAICompletionsHandler):
    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_style = ModelStyle.OPENAI_COMPLETIONS
        self.client = OpenAI(
            base_url= os.getenv("MINING_BASE_URL"),
            api_key=os.getenv("MINING_API_KEY"),
        )

    def decode_ast(self, result, language, has_tool_call_tag):
        decoded_output = []
        for invoked_function in result:
            name = invoked_function["name"]
            params = invoked_function["arguments"]
            decoded_output.append({name: params})
        return decoded_output

    def decode_execute(self, result, has_tool_call_tag):
        too_call_format = []
        for tool_call in result:
            if isinstance(tool_call, dict):
                name = tool_call.get("name", "")
                arguments = tool_call.get("arguments", {})
                args_str = ", ".join(
                    [f"{key}={repr(value)}" for key, value in arguments.items()]
                )
                too_call_format.append(f"{name}({args_str})")
        return too_call_format
