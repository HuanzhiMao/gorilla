import json
from pathlib import Path
from mistral_local_handler import MistralHandler
from typing import List, Dict

class MathAPI:
    def mean(self, numbers: List[float]) -> Dict[str, float]:
        if not numbers:
            return {"error": "Cannot calculate mean of an empty list"}
        return {"result": sum(numbers) / len(numbers)}

    def standard_deviation(self, numbers: List[float]) -> Dict[str, float]:
        if not numbers:
            return {"error": "Cannot calculate standard deviation of an empty list"}
        mean = sum(numbers) / len(numbers)
        variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
        return {"result": variance ** 0.5}

    def add(self, a: float, b: float) -> Dict[str, float]:
        return {"result": a + b}

    def multiply(self, a: float, b: float) -> Dict[str, float]:
        return {"result": a * b}

def main():
    # Initialize handler
    handler = MistralHandler(
        model_name="/data/amitojsingh/mistral_models/7B-Instruct-v0.3",
        temperature=0.7
    )
    math_api = MathAPI()

    # Available functions for the handler
    functions = [math_api.mean, math_api.standard_deviation, math_api.add, math_api.multiply]

    # Predefined single-question queries
    queries = [
        "Calculate the mean of: 1, 2, 3, 4, 5",
        "Add 5 and 3",
        "What's the standard deviation of 10, 20, 30, 40?",
        "Multiply 12.5 and 8.3"
    ]

    # Result storage
    results = []
    output_file_path = Path("function_call_results.json")

    for query in queries:
        # Single-turn conversation for each query
        messages = [
            {"role": "system", "content": "You are a mathematical assistant."},
            {"role": "user", "content": query}
        ]

        try:
            # Run inference with the handler
            result = handler.inference(messages, functions)
            raw_response = result["response"]

            # Decode AST (function calls)
            function_calls = handler.decode_ast(raw_response)
            execution_results = []

            # Process the function calls and execute
            for func_call in function_calls:
                if "name" in func_call and "arguments" in func_call:
                    result = handler.process_tool_calls(func_call, math_api)
                    execution_results.append(result)
                else:
                    execution_results.append({"error": "Malformed function call"})

            # Append the result for this query
            results.append({
                "query": query,
                "raw_response": raw_response,
                "function_calls": function_calls,
                "execution_results": execution_results
            })

        except Exception as e:
            # Handle errors gracefully
            results.append({"query": query, "error": str(e)})

    # Save results to an external file
    with output_file_path.open("w") as f:
        json.dump(results, f, indent=4)

    print(f"Results written to {output_file_path}")

if __name__ == "__main__":
    main()
