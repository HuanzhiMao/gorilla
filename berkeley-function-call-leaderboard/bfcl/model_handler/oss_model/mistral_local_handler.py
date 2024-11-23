import json
import re
from typing import Dict, List, Any
from pathlib import Path
import inspect
from base_transformer_handler import BaseTransformerHandler

class MistralHandler(BaseTransformerHandler):
    def __init__(self, model_name: str, temperature: float = 0.7) -> None:
        super().__init__(model_name, temperature)
        self.load_model(model_name)

    def _format_function_schema(self, func: Any) -> Dict[str, Any]:
        """Create a JSON schema for a function."""
        sig = inspect.signature(func)
        docstring = inspect.getdoc(func)
        
        description = docstring.split('Args:')[0].strip() if docstring else ""
        properties = {}
        required = []
        
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            param_type = param.annotation
            param_schema = {"type": str(param_type).lower()}
            properties[param_name] = param_schema
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        return {
            "name": func.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required
            }
        }

    def _format_prompt(self, messages: List[Dict[str, str]], functions: List[Dict]) -> str:
        """Format the conversation and functions into Mistral's expected prompt format."""
        prompt = ""
        if messages and messages[0]["role"] == "system":
            system_message = messages[0]["content"]
            messages = messages[1:]
        else:
            system_message = "You are a helpful assistant that uses function calls."

        # Start with system message
        prompt += f"<|im_start|>system\n{system_message}\n<|im_end|>\n\n"

        # Add function schemas
        prompt += "Available functions:\n"
        for func in functions:
            prompt += f"{json.dumps(func, indent=2)}\n\n"

        # Provide an example usage to guide the model
        example_query = "What is the mean of 1, 2, 3?"
        example_call = json.dumps({
            "name": "mean",
            "arguments": {"numbers": [1, 2, 3]}
        })
        prompt += f"<|im_start|>user\n{example_query}\n<|im_end|>\n<|im_start|>assistant\n{example_call}\n<|im_end|>\n\n"

        # Add conversation messages
        for message in messages:
            role = message["role"]
            content = message["content"]
            prompt += f"<|im_start|>{role}\n{content}\n<|im_end|>\n"

        return prompt


    def decode_ast(self, result: str) -> List[Dict[str, Any]]:
        """Decode model output into function calls or fallback to parsing natural language."""
        decoded_calls = []
        try:
            # Split the response by role delimiters
            segments = result.split("<|im_start|>")
            for segment in segments:
                # Attempt to find JSON blocks
                if "{" in segment and "}" in segment:
                    start = segment.find("{")
                    end = segment.rfind("}") + 1
                    json_str = segment[start:end]
                    try:
                        function_call = json.loads(json_str)
                        if "name" in function_call and "arguments" in function_call:
                            decoded_calls.append(function_call)
                    except json.JSONDecodeError:
                        continue  # Skip invalid JSON

            # Fallback to natural language parsing if no JSON was found
            if not decoded_calls:
                decoded_calls = self._fallback_parse(result)

        except Exception as e:
            print(f"Error decoding AST: {e}")
        return decoded_calls

    def _fallback_parse(self, response: str) -> List[Dict[str, Any]]:
        """Fallback to parse natural language responses for function calls."""
        function_calls = []
        try:
            # Simple regex patterns for common operations
            if "add" in response.lower() or "+" in response:
                match = re.findall(r"(\d+\.?\d*)", response)
                if len(match) == 2:
                    function_calls.append({
                        "name": "add",
                        "arguments": {"a": float(match[0]), "b": float(match[1])}
                    })
            elif "mean" in response.lower():
                numbers = re.findall(r"(\d+\.?\d*)", response)
                if numbers:
                    function_calls.append({
                        "name": "mean",
                        "arguments": {"numbers": [float(n) for n in numbers]}
                    })
            elif "standard deviation" in response.lower():
                numbers = re.findall(r"(\d+\.?\d*)", response)
                if numbers:
                    function_calls.append({
                        "name": "standard_deviation",
                        "arguments": {"numbers": [float(n) for n in numbers]}
                    })
            elif "multiply" in response.lower() or "*" in response:
                match = re.findall(r"(\d+\.?\d*)", response)
                if len(match) == 2:
                    function_calls.append({
                        "name": "multiply",
                        "arguments": {"a": float(match[0]), "b": float(match[1])}
                    })
        except Exception as e:
            print(f"Error in fallback parsing: {e}")
        return function_calls

    def decode_execute(self, result: str) -> List[str]:
        """Convert model output into executable commands."""
        execution_list = []
        try:
            if "<tool_call>" in result:
                tool_calls = result.split("<tool_call>")
                for call in tool_calls[1:]:
                    if "</tool_call>" in call:
                        call_json = call.split("</tool_call>")[0]
                        function_call = json.loads(call_json)
                        name = function_call["name"]
                        params = function_call["arguments"]
                        param_str = ",".join([f"{k}={repr(v)}" for k, v in params.items()])
                        execution_list.append(f"{name}({param_str})")
        except Exception as e:
            print(f"Error formatting execution calls: {e}")
        return execution_list
