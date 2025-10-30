import re
import os
from openai import OpenAI

#### Main functions ####

GRADER_TEMPLATE = """
Judge whether the following [response] to [question] is correct or not based on the precise and unambiguous [correct_answer] below.

[question]: {question}

[response]: {response}

Your judgement must be in the format and criteria specified below:

extracted_final_answer: The final exact answer extracted from the [response]. Put the extracted answer as 'None' if there is no exact, final answer to extract from the response.

[correct_answer]: {correct_answer}

reasoning: Explain why the extracted_final_answer is correct or incorrect based on [correct_answer], focusing only on if there are meaningful differences between [correct_answer] and the extracted_final_answer. Do not comment on any background to the problem, do not attempt to solve the problem, do not argue for any answer different than [correct_answer], focus only on whether the answers match.

correct: Answer 'yes' if extracted_final_answer matches the [correct_answer] given above, or is within a small margin of error for numerical problems. Answer 'no' otherwise, i.e. if there if there is any inconsistency, ambiguity, non-equivalency, or if the extracted answer is incorrect.


confidence: The extracted confidence score between 0|\%| and 100|\%| from [response]. Put 100 if there is no confidence score available.
""".strip()

CHOICE_STRINGS = ["yes", "no"]


def agentic_checker(model_response: str, possible_answer_list: list[str], question) -> dict:
    """
    Check if one of the possible answers is contained in the model response, ignoring case, whitespace and ",./-_*^" punctuation.
    """
    grader_prompt = GRADER_TEMPLATE.format(
        question=question,
        correct_answer=possible_answer_list[0],
        response=model_response,
    )

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.responses.create(
        model="gpt-5",
        input=grader_prompt,
    )
    grading_response = response.output_text

    match = re.search(r"correct: (yes|no)", grading_response)
    if match:
        if match.group(1) == "yes":
            return {"valid": True, "error": []}
        else:
            return {
                "valid": False,
                "error": [grading_response],
                "details": {
                    "model_response": model_response,
                    "possible_answers": possible_answer_list,
                },
            }

    else:
        return {
            "valid": False,
            "error": [grading_response],
            "error_type": "agentic:grading_error",
            "details": {
                "model_response": model_response,
                "possible_answers": possible_answer_list,
            },
        }

    standardized_possible_answer_list = [
        standardize_string(possible_answer) for possible_answer in possible_answer_list
    ]
    # Sometimes the model response is a list of one string
    if type(model_response) is list:
        model_response = model_response[0]
    if type(model_response) is not str:
        model_response = str(model_response)

    standardized_model_response = standardize_string(model_response)

    for possible_answer in standardized_possible_answer_list:
        if re.search(rf"\b{re.escape(possible_answer)}\b", standardized_model_response):
            return {"valid": True, "error": []}

    return {
        "valid": False,
        "error_message": f"None of the expected answers were found in the model response.",
        "error_type": "agentic:answer_not_found",
        "details": {
            "model_response": model_response,
            "possible_answers": possible_answer_list,
            "standardized_model_response": standardized_model_response,
            "standardized_possible_answers": standardized_possible_answer_list,
        },
    }


#### Helper functions ####


def standardize_string(input_string: str):
    """
    This function standardizes the string by removing all the whitespace, ",./-_*^()" punctuation, and converting it to lowercase
    It will also convert all the single quotes to double quotes
    This is used to compare the model output with the possible answers
    We don't want to punish model for answer like April 1, 2024 vs April 1,2024, vs April 1 2024
    """
    regex_string = r"[\,\.\/\-\_\*\^\(\)]"
    return re.sub(regex_string, "", input_string).lower().replace("'", '"')
