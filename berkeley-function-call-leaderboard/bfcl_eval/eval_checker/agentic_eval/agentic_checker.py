import ast
import json
import re
from typing import Optional

#### Main functions ####


def agentic_checker(model_response: str, possible_answer_list: list[str]) -> dict:
    """
    Extract the structured {'answer': ...} dict from the model response and check if the
    'answer' field matches one of the possible answers (ignoring case, whitespace, and punctuation).
    If extraction fails, the response is marked as invalid (0 score).
    """
    standardized_possible_answer_list = [
        standardize_string(possible_answer) for possible_answer in possible_answer_list
    ]
    # Sometimes the model response is a list of one string
    if type(model_response) is list:
        model_response = model_response[0] if model_response else ""
    if type(model_response) is not str:
        model_response = str(model_response)

    # Extract the structured answer field
    extracted_answer = extract_answer_field(model_response)
    if extracted_answer is None:
        return {
            "valid": False,
            "error_message": "Could not extract a structured {'answer': ...} dict from the model response.",
            "error_type": "agentic:answer_extraction_failed",
            "details": {
                "model_response": model_response,
                "possible_answers": possible_answer_list,
            },
        }

    standardized_extracted = standardize_string(str(extracted_answer))
    for possible_answer in standardized_possible_answer_list:
        # A candidate can start/end with currency, percent signs, brackets, or
        # quotation marks. Word boundaries require a word character on one side,
        # so they reject even an exact "$12" or "2.3%" answer. Check the characters
        # outside the entire candidate instead, while still rejecting 21 in 121
        # and names embedded in longer words.
        if possible_answer and re.search(
            rf"(?<!\w){re.escape(possible_answer)}(?!\w)", standardized_extracted
        ):
            return {"valid": True, "error": []}

    return {
        "valid": False,
        "error_message": "The extracted answer field did not match any of the expected answers.",
        "error_type": "agentic:answer_not_found",
        "details": {
            "model_response": model_response,
            "extracted_answer": extracted_answer,
            "possible_answers": possible_answer_list,
            "standardized_extracted_answer": standardized_extracted,
            "standardized_possible_answers": standardized_possible_answer_list,
        },
    }


#### Helper functions ####


def extract_answer_field(model_response: str) -> Optional[str]:
    """
    Try to extract the 'answer' field from a structured dict in the model response.
    The model is prompted to output: {'answer': ..., 'context': ...}
    Returns the answer value as a string, or None if extraction fails.
    """
    # Find all dict-like patterns containing 'answer' key
    # Matches both {'answer': ...} and {"answer": ...}
    # Use a greedy search from the last occurrence (models tend to put the final answer at the end)
    candidates = list(re.finditer(r"\{[^{}]*['\"]answer['\"]", model_response))
    if not candidates:
        return None

    for match in reversed(candidates):
        start = match.start()
        # Find the matching closing brace
        brace_depth = 0
        end = None
        for i in range(start, len(model_response)):
            if model_response[i] == '{':
                brace_depth += 1
            elif model_response[i] == '}':
                brace_depth -= 1
                if brace_depth == 0:
                    end = i + 1
                    break
        if end is None:
            continue

        dict_str = model_response[start:end]

        # Try parsing as Python literal first (handles single quotes)
        try:
            parsed = ast.literal_eval(dict_str)
            if isinstance(parsed, dict) and "answer" in parsed:
                return str(parsed["answer"])
        except (ValueError, SyntaxError):
            pass

        # Try parsing as JSON (handles double quotes)
        try:
            parsed = json.loads(dict_str)
            if isinstance(parsed, dict) and "answer" in parsed:
                return str(parsed["answer"])
        except (json.JSONDecodeError, ValueError):
            pass

    return None


def standardize_string(input_string: str):
    """
    Normalize case, the benchmark's ignored punctuation, and whitespace.

    Keep word separation: removing every space would let unrelated words merge
    into a candidate. Currency and percent signs remain part of the answer.
    """
    regex_string = r"[\,\.\/\-\_\*\^\(\)\"']"
    return " ".join(re.sub(regex_string, "", input_string).lower().split())
