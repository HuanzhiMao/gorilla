import ast
import re

from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import (
    execute_multi_turn_func_call,
    is_empty_execute_response,
)

#### Main functions ####


def multi_turn_checker(
    multi_turn_model_result_list_decoded: list[list[list[str]]],
    multi_turn_ground_truth_list: list[list[str]],
    test_entry: dict,
    test_category: str,
    model_name: str,
) -> dict:
    """
    The main function that checks the correctness of the model's function call execution.
    """

    initial_config: dict = test_entry["initial_config"]
    involved_classes: list = test_entry["involved_classes"]
    test_entry_id: str = test_entry["id"]
    test_category: str = test_entry_id.rsplit("_", 1)[0]
    execution_results: list[dict] = []
    all_turn_model_execution_results: list[dict] = []

    # First execute all the function calls
    for turn_index, single_turn_ground_truth_list in enumerate(
        multi_turn_ground_truth_list
    ):
        single_turn_model_response_list = multi_turn_model_result_list_decoded[turn_index]

        # Note that we combine all the sub-step results into a single list, for easier comparison
        single_turn_model_execution_results = []
        single_turn_model_execution_results_uncombined = []
        single_turn_ground_truth_execution_results = []
        model_instances = {}  # Will be overwritten in the for loop
        single_step_model_execution_results = []  # Will be overwritten in the for loop
    
        for single_step_model_response in single_turn_model_response_list:
            single_step_model_execution_results, model_instances = (
                execute_multi_turn_func_call(
                    func_call_list=single_step_model_response,
                    initial_config=initial_config,
                    involved_classes=involved_classes,
                    model_name=model_name,
                    test_entry_id=test_entry_id,
                    long_context=(
                        "long_context" in test_category or "composite" in test_category
                    ),
                    is_evaL_run=True,
                )
            )
            single_turn_model_execution_results.extend(single_step_model_execution_results)
            single_turn_model_execution_results_uncombined.append(single_step_model_execution_results)

        # Execute the ground truth function calls
        single_turn_ground_truth_execution_results, ground_truth_instances = (
            execute_multi_turn_func_call(
                func_call_list=single_turn_ground_truth_list,
                initial_config=initial_config,
                involved_classes=involved_classes,
                model_name=model_name + "_ground_truth",
                test_entry_id=test_entry_id,
                long_context=(
                    "long_context" in test_category or "composite" in test_category
                ),
                is_evaL_run=True,
            )
        )

        all_turn_model_execution_results.extend(single_turn_model_execution_results)
        execution_results.append(
            {
                "model": single_turn_model_execution_results_uncombined,
                "ground_truth": single_turn_ground_truth_execution_results,
            }
        )

        # If the ground truth list is not empty, then the model response list should not be empty
        if len(single_turn_ground_truth_list) > 0:
            if not single_turn_model_response_list or is_empty_execute_response(
                single_turn_model_response_list
            ):
                return {
                    "valid": False,
                    "error_message": f"Model response list is empty for turn {turn_index}",
                    "error_type": "multi_turn:empty_turn_model_response",
                    "details": {
                        "execution_result": execution_results,
                    },
                }

        # If the ground truth list is empty, this is the turn where the model should eventually fail to achieve the user request.
        # The actual check for irrelevance is done in the multi_turn_irrelevance_checker function
        # Note: If the model outputs any function call in this turn, we will still execute it so that the state check at the next turn is accurate.
        if not single_turn_ground_truth_list:
            continue

        ## Check after each turn ##
        assert len(model_instances) == len(
            ground_truth_instances
        ), f"Model instances and ground truth instances do not match in length for turn {turn_index}. Model instances: {len(model_instances)}, Ground truth instances: {len(ground_truth_instances)}"
        assert set(model_instances.keys()) == set(ground_truth_instances.keys())

        # Check the state of the instances
        state_check_result = state_checker(model_instances, ground_truth_instances)
        if not state_check_result["valid"]:
            state_check_result["execution_result"] = execution_results
            return state_check_result

        # Check the response of the function calls
        # We use the all_turn_model_execution_results to accomodate the situation where the model invokes a function in a previous turn, and thus don't need to invoke it again in the current turn.
        response_check_result = response_checker(
            all_turn_model_execution_results,
            single_turn_ground_truth_execution_results,
            turn_index,
        )
        if not response_check_result["valid"]:
            return response_check_result

        # # Check the method invoke order
        # method_invoke_order_check_result = method_invoke_order_checker(
        #     model_instances, ground_truth_instances
        # )
        # if not method_invoke_order_check_result["valid"]:
        #     return method_invoke_order_check_result

    return {"valid": True}


def multi_turn_irrelevance_checker(
    multi_turn_model_result_list_decoded: list[list[list[str]]],
    multi_turn_ground_truth_list: list[list[str]],
) -> dict:
    """
    Check if the model's output are irrelevant when it should be.
    It should be empty when the ground truth is a empty list for that turn.
    """
    for turn_index, single_turn_ground_truth_list in enumerate(
        multi_turn_ground_truth_list
    ):
        single_turn_model_response_list = multi_turn_model_result_list_decoded[turn_index]
        if len(single_turn_ground_truth_list) == 0:
            if is_empty_execute_response(single_turn_model_response_list):
                continue
            else:
                return {
                    "valid": False,
                    "error_message": f"Model outputs valid function calls when it should not for turn {turn_index}.",
                    "error_type": "multi_turn:irrelevance_error:decoder_success",
                    "details": {
                        "model response decoded": single_turn_model_response_list,
                    },
                }
    return {"valid": True}


#### Sub-Chekcers ####


def state_checker(model_instances: dict, ground_truth_instances: dict):
    """
    Checks if, after executing the function calls, the model_instance has the same state (defined by the attributes) as the ground_truth_instance.
    It checks if every instance in the model_instances has the same attributes as their corresponding instance (of the same class) from ground_truth_instances.
    """
    for class_name, ground_truth_instance in ground_truth_instances.items():
        model_instance = model_instances[class_name]
        valid, differences = _compare_instances(model_instance, ground_truth_instance)

        if not valid:
            model_instance_attributes = {
                key: value
                for key, value in vars(model_instance).items()
                if not key.startswith("_")
            }
            ground_truth_instance_attributes = {
                key: value
                for key, value in vars(ground_truth_instance).items()
                if not key.startswith("_")
            }
            # Format the error message for better readability
            return {
                "valid": False,
                "error_message": f"Model instance for {class_name} does not match the state with ground truth instance.",
                "error_type": "multi_turn:instance_state_mismatch",
                "details": {
                    "differences": differences,
                    "model_instance_state": model_instance_attributes,
                    "ground_truth_instance_state": ground_truth_instance_attributes,
                },
            }

    return {"valid": True}


def response_checker(
    model_response_list: list, ground_truth_response_list: list, turn_index: int
):
    """
    Checks if the model_response is a subsequence of the ground_truth_response.
    Each list contains the response of the function calls executed in that single turn.
    """
    # We don't need to enforce the order of the responses, because many entries have parallel operations, and so the model can execute them in any order.
    is_subsequence, missing_items = _is_subsequence_unordered(
        ground_truth_response_list, model_response_list
    )
    if not is_subsequence:
        return {
            "valid": False,
            "error_message": f"Model response execution results so far does not contain all the ground truth response execution results for turn {turn_index}.",
            "error_type": "multi_turn:execution_response_mismatch",
            "details": {
                "missing_items": missing_items,
                "model_response (including all previous turns)": model_response_list,
                "ground_truth_response (only the current turn)": ground_truth_response_list,
            },
        }

    return {"valid": True}


def method_invoke_order_checker(model_instances: dict, ground_truth_instances: dict):
    """
    Checks if the model_instance called the same order of methods as the ground_truth_instance.
    model_instance can call additional methods, but not skip any method that the ground_truth_instance called.

    Note: Currently, this functions only checks for the method names and not the arguments.
    """
    for class_name, ground_truth_instance in ground_truth_instances.items():
        model_instance = model_instances[class_name]

        # The get_method_called method is added by the LoggingMeta metaclass automatically
        model_invoke_order = model_instance.get_method_called()
        ground_truth_invoke_order = ground_truth_instance.get_method_called()

        # Extract the method names
        model_invoke_order = [method_call["method"] for method_call in model_invoke_order]
        ground_truth_invoke_order = [
            method_call["method"] for method_call in ground_truth_invoke_order
        ]

        is_subsequence, missing_items = _is_subsequence(
            ground_truth_invoke_order, model_invoke_order
        )
        if not is_subsequence:
            return {
                "valid": False,
                "error_message": f"Model instance for {class_name} does not match the method invoke order with ground truth instance. Missing items: {missing_items}",
                "error_type": "multi_turn:method_invoke_order_mismatch",
            }

    return {"valid": True}


#### Helper functions ####


def _compare_instances(model_obect, ground_truth_object):
    """
    Checks if the model_object has the same attributes as the ground_truth_object. They are instances of the same class.
    """
    assert type(model_obect) == type(
        ground_truth_object
    ), "Objects are not of the same type."
    differences = {}
    valid = True
    for attr_name in vars(ground_truth_object):
        # We don't check for private attributes
        if attr_name.startswith("_"):
            continue
        model_attr = getattr(model_obect, attr_name)
        ground_truth_attr = getattr(ground_truth_object, attr_name)

        if model_attr != ground_truth_attr:
            valid = False
            differences[attr_name] = {"model": model_attr, "ground_truth": ground_truth_attr}

    return valid, differences


def _is_subsequence(list1, list2) -> tuple[bool, list]:
    """
    Checks if list1 is a subsequence of list2, i.e., all elements of list1 are present in list2 in the same order.
    Also returns the elements of list1 that are not present in list2.
    """
    # Convert list2 to an iterator to ensure that the elements are consumed only once.
    iter_list2 = iter(list2)
    return all(item in iter_list2 for item in list1), [
        item for item in list1 if item not in list2
    ]


def _is_subsequence_unordered(list1, list2) -> tuple[bool, list]:
    """
    Checks if all elements of list1 are present in list2, regardless of order.
    Also returns the elements of list1 that are not present in list2.
    """
    # Copy list2 to avoid modifying the original list during checks
    list2_copy = list2[:]
    
    # Check each item in list1 to see if it exists in list2_copy
    missing_elements = []
    for item in list1:
        try:
            # Attempt to remove one occurrence of `item` from list2_copy to handle duplicates
            list2_copy.remove(item)
        except ValueError:
            # If item is not found, add it to missing_elements
            missing_elements.append(item)
    
    # If there are missing elements, list1 is not a subsequence of list2
    is_subsequence = len(missing_elements) == 0
    return is_subsequence, missing_elements


#### Function Call Constraint Checker ####


def multi_turn_func_call_constraint_checker(
    multi_turn_model_result_list_decoded: list[list[list[str]]],
    ground_truth: dict,
) -> dict:
    """
    Checks the model's function calls against must_be_called and must_not_be_called constraints.

    Args:
        multi_turn_model_result_list_decoded: The decoded model responses across turns.
            Structure: list[turns] -> list[steps] -> list[func_call_strings]
        ground_truth: A dict with keys:
            - "must_be_called_functions": list of function specs that must appear in order.
            - "must_not_be_called_functions": list of function specs that must not appear.

    Each function spec is either:
        - "ClassName.method_name" — only checks that the method was called (args ignored)
        - "ClassName.method_name(arg1=val1, arg2=val2)" — checks that the method was called
          with at least the listed arguments matching the listed values (extra args are ok)
    """
    must_be_called = ground_truth.get("must_be_called_functions", [])
    must_not_be_called = ground_truth.get("must_not_be_called_functions", [])

    # Flatten all model function calls across turns and steps into a single ordered list
    all_model_calls = []
    for turn in multi_turn_model_result_list_decoded:
        for step in turn:
            for func_call in step:
                all_model_calls.append(func_call)

    # Parse the constraint specs
    must_be_called_specs = [_parse_func_spec(spec) for spec in must_be_called]
    must_not_be_called_specs = [_parse_func_spec(spec) for spec in must_not_be_called]

    # Check must_be_called: must appear as a subsequence (in order, other calls allowed in between)
    must_be_called_result = _check_must_be_called(all_model_calls, must_be_called_specs)
    if not must_be_called_result["valid"]:
        return must_be_called_result

    # Check must_not_be_called: none of these should appear
    must_not_be_called_result = _check_must_not_be_called(
        all_model_calls, must_not_be_called_specs
    )
    if not must_not_be_called_result["valid"]:
        return must_not_be_called_result

    return {"valid": True}


def _parse_func_spec(spec: str) -> dict:
    """
    Parse a function constraint spec into its components.

    Supports:
        "ClassName.method_name" -> {"class": "ClassName", "method": "method_name", "args": None}
        "ClassName.method_name(a=1, b='x')" -> {"class": "ClassName", "method": "method_name", "args": {"a": 1, "b": "x"}}
        "method_name" -> {"class": None, "method": "method_name", "args": None}
        "method_name(a=1)" -> {"class": None, "method": "method_name", "args": {"a": 1}}
    """
    # Split off args portion if present
    paren_idx = spec.find("(")
    if paren_idx != -1:
        name_part = spec[:paren_idx]
        args_str = spec[paren_idx:]  # includes parens
        args = _parse_args(args_str)
    else:
        name_part = spec
        args = None

    # Split class and method
    if "." in name_part:
        class_name, method_name = name_part.rsplit(".", 1)
    else:
        class_name = None
        method_name = name_part

    return {
        "class": class_name,
        "method": method_name,
        "args": args,
        "raw": spec,
    }


def _parse_args(args_str: str) -> dict:
    """
    Parse an argument string like "(query='hello', max_results=10)" into a dict.
    Uses ast to safely evaluate the argument values.
    """
    # Wrap in a dummy function call so ast can parse it
    dummy_call = f"f{args_str}"
    try:
        tree = ast.parse(dummy_call, mode="eval")
        call_node = tree.body
        args = {}
        # Handle keyword arguments
        for kw in call_node.keywords:
            args[kw.arg] = ast.literal_eval(kw.value)
        # Handle positional arguments (store by index)
        for i, arg in enumerate(call_node.args):
            args[i] = ast.literal_eval(arg)
        return args
    except (SyntaxError, ValueError):
        return {}


def _parse_model_call(func_call: str) -> dict:
    """
    Parse a model function call string into method name and arguments.

    Model calls can be:
        "method_name(arg1=val1, ...)"
        "ClassName.method_name(arg1=val1, ...)"
    """
    paren_idx = func_call.find("(")
    if paren_idx != -1:
        name_part = func_call[:paren_idx].strip()
        args_str = func_call[paren_idx:]
        args = _parse_args(args_str)
    else:
        name_part = func_call.strip()
        args = {}

    if "." in name_part:
        class_name, method_name = name_part.rsplit(".", 1)
    else:
        class_name = None
        method_name = name_part

    return {
        "class": class_name,
        "method": method_name,
        "args": args,
    }


def _func_call_matches_spec(func_call: str, spec: dict) -> bool:
    """
    Check if a model function call string matches a constraint spec.

    Matching rules:
    - Method name must match.
    - If spec has a class name, the model call's class must match (if present) or is ignored
      (since model calls may not include class prefixes).
    - If spec has args, every arg in the spec must be present in the model call with the same value.
      The model call may have additional args.
    """
    parsed = _parse_model_call(func_call)

    # Method name must match
    if parsed["method"] != spec["method"]:
        return False

    # Note: spec may have a class name (e.g. "WeatherCom.login") but that's purely for
    # human readability. Model calls never include class prefixes, so we don't check it.

    # If spec has no args requirement, we're done (just checking the function was called)
    if spec["args"] is None:
        return True

    # Check that all spec args are present in the model call with matching values
    for key, expected_value in spec["args"].items():
        if key not in parsed["args"]:
            return False
        if parsed["args"][key] != expected_value:
            return False

    return True


def _check_must_be_called(
    all_model_calls: list[str], specs: list[dict]
) -> dict:
    """
    Check that all specs appear as a subsequence of the model calls (in order).
    The model can call other functions in between.
    """
    if not specs:
        return {"valid": True}

    spec_idx = 0
    for func_call in all_model_calls:
        if spec_idx >= len(specs):
            break
        if _func_call_matches_spec(func_call, specs[spec_idx]):
            spec_idx += 1

    if spec_idx < len(specs):
        missing = [spec["raw"] for spec in specs[spec_idx:]]
        return {
            "valid": False,
            "error_message": f"Required function calls not found (in order) in model response. Missing: {missing}",
            "error_type": "multi_turn:must_be_called_missing",
            "details": {
                "missing_specs": missing,
                "model_calls": all_model_calls,
            },
        }

    return {"valid": True}


def _check_must_not_be_called(
    all_model_calls: list[str], specs: list[dict]
) -> dict:
    """
    Check that none of the specs match any model call.
    """
    for func_call in all_model_calls:
        for spec in specs:
            if _func_call_matches_spec(func_call, spec):
                return {
                    "valid": False,
                    "error_message": f"Function call '{func_call}' matches forbidden spec '{spec['raw']}'.",
                    "error_type": "multi_turn:must_not_be_called_violation",
                    "details": {
                        "matched_call": func_call,
                        "forbidden_spec": spec["raw"],
                        "model_calls": all_model_calls,
                    },
                }

    return {"valid": True}
