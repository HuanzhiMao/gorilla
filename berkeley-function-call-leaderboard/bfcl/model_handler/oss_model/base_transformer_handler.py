from abc import ABC, abstractmethod
import json
from typing import Dict, List, Any, Optional
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from pathlib import Path

class BaseTransformerHandler(ABC):
    def __init__(self, model_name: str, temperature: float = 0.7) -> None:
        """
        Initialize base transformer handler.
        
        Args:
            model_name: Name or path of the model
            temperature: Temperature for generation
        """
        self.model_name = model_name
        self.temperature = temperature
        self.model = None
        self.tokenizer = None
        
    def load_model(self, model_path: str):
        """Load the model and tokenizer."""
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            
            # Ensure the pad token is set
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.bfloat16,
                device_map="auto"
            )
        except Exception as e:
            raise Exception(f"Error loading model: {str(e)}")

    @abstractmethod
    def _format_function_schema(self, func: Any) -> Dict[str, Any]:
        """Create JSON schema for a function."""
        pass

    @abstractmethod
    def _format_prompt(self, messages: List[Dict[str, str]], functions: List[Dict]) -> str:
        """Format the conversation and functions into expected prompt format."""
        pass

    @abstractmethod
    def decode_ast(self, result: str) -> List[Dict[str, Any]]:
        """Decode model output into function calls."""
        pass

    @abstractmethod
    def decode_execute(self, result: str) -> List[str]:
        """Convert model output into executable commands."""
        pass

    def inference(self, 
                 messages: List[Dict[str, str]], 
                 functions: List[Any],
                 include_input_log: bool = False,
                 include_state_log: bool = False) -> Dict[str, Any]:
        """
        Run inference with the model.
        
        Args:
            messages: Conversation messages
            functions: Available functions
            include_input_log: Whether to include input logs
            include_state_log: Whether to include state logs
        
        Returns:
            Dict containing model response and metadata
        """
        function_schemas = [self._format_function_schema(func) for func in functions]
        prompt = self._format_prompt(messages, function_schemas)
        
        try:
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=512
            )
            
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=300,
                do_sample=True,
                temperature=self.temperature,
                pad_token_id=self.tokenizer.eos_token_id
            )
            
            response = self.tokenizer.decode(
                outputs[0][inputs["input_ids"].shape[1]:],
                skip_special_tokens=False
            )
            
            metadata = {
                "input_tokens": inputs["input_ids"].shape[1],
                "output_tokens": outputs.shape[1] - inputs["input_ids"].shape[1]
            }
            
            if include_input_log:
                metadata["input_log"] = {"prompt": prompt}
                
            if include_state_log:
                metadata["state_log"] = {"messages": messages}
            
            return {
                "response": response,
                "metadata": metadata
            }
        except Exception as e:
            raise Exception(f"Inference error: {str(e)}")

    def process_tool_calls(self, 
                          tool_call: Dict[str, Any], 
                          math_api: Any) -> Optional[Dict[str, Any]]:
        """Process and execute tool calls."""
        try:
            function_name = tool_call["name"]
            arguments = tool_call["arguments"]
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            
            func = getattr(math_api, function_name, None)
            if func is None:
                return None
                
            return func(**arguments)
        except Exception as e:
            return None