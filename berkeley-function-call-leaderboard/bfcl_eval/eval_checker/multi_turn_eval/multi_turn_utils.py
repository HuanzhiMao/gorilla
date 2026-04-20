import copy
import importlib
import importlib.util
import inspect
import json
import keyword
import re

from bfcl_eval.constants.eval_config import SERVER_FAILURE_PATCH_PATH
from bfcl_eval.constants.executable_backend_config import (
    CLASS_FILE_PATH_MAPPING,
    STATELESS_CLASSES,
)
from bfcl_eval.constants.enums import ResultType
from bfcl_eval.eval_checker.multi_turn_eval.func_source_code import ImageResult

def load_all_server_patches():
    """
    Import all patch modules from SERVER_FAILURE_PATCH_PATH so that their
    @_register_patch decorators execute and populate the class patch registries.

    Call this once from the main thread before dispatching worker threads —
    registering patches mutates class state and is not thread-safe.
    """
    if not SERVER_FAILURE_PATCH_PATH.is_dir():
        return

    for patch_file in sorted(SERVER_FAILURE_PATCH_PATH.glob("*.py")):
        if patch_file.name.startswith("_"):
            continue
        spec = importlib.util.spec_from_file_location(patch_file.stem, patch_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)


def _apply_failure_injections(involved_instances: dict, failure_injection: list):
    """
    Apply server-failure patches to the given class instances.

    Args:
        involved_instances: Mapping of class name -> instance.
        failure_injection: A list of {"method": ClassName.method_name, "patch": patch_name} dicts.
            e.g. [{"method": "WeatherComAPI.compare_locations", "patch": "FEATURE_SUSPENDED"}]
    """
    for spec in failure_injection:
        class_method, patch_name = spec["method"], spec["patch"]
        class_name, method_name = class_method.rsplit(".", 1)
        if class_name not in involved_instances:
            raise ValueError(
                f"failure_injection references class '{class_name}' "
                f"but it is not in involved_classes: {sorted(involved_instances)}"
            )
        involved_instances[class_name]._apply_patch(method_name, patch_name)


def execute_multi_turn_func_call(
    func_call_list: list[str],  # a list of strings of func calls
    initial_config: dict,
    involved_classes: list,
    model_name: str,
    test_entry_id: str,
    long_context: bool = False,
    is_evaL_run: bool = False,
    failure_injection: list | None = None,
) -> tuple[list[dict], dict]:
    """
    Execute a list of function calls against dynamically loaded class instances.

    For each class in `involved_classes`, this function loads (or reuses) a unique class instance,
    configures it with `initial_config`, and maps its public methods by name. Each string in
    `func_call_list` is then resolved to the appropriate instance and evaluated via `eval()`.

    Instances are cached in `globals()` keyed by model name, test entry ID, and class name,
    so subsequent turns reuse the same stateful instances.

    Args:
        func_call_list: A list of function call strings to execute (e.g. ["get_weather(city='SF')"]).
        initial_config: A dict mapping class names to their initial scenario configuration.
        involved_classes: A list of class name strings to instantiate and expose methods from.
        model_name: The model name, used as part of the instance cache key.
        test_entry_id: The test entry ID, used as part of the instance cache key.
        long_context: Whether to load the scenario in long-context mode.
        is_evaL_run: If True, appends "_eval" to the model name for cache isolation.
        failure_injection: Optional list of {"method": ClassName.method_name, "patch": patch_name} dicts
            to apply after instance creation (turn 0 only).

    Returns:
        A tuple of (execution_results, involved_instances) where:
        - execution_results is a list of dicts, each with "result" (str or dict) and
          "result_type" (ResultType.TEXT or ResultType.IMAGE).
        - involved_instances is a dict mapping class names to their instantiated objects.
    """
    if is_evaL_run:
        model_name += "_eval"

    class_method_name_mapping = {}
    involved_instances = {}
    newly_created = False
    for class_name in involved_classes:
        module_name = CLASS_FILE_PATH_MAPPING[class_name]
        instance_name = f"{model_name}_{test_entry_id}_{class_name}_instance"
        instance_name = _sanitize_class_instance_name(instance_name)
        if instance_name not in globals():
            newly_created = True
            module = importlib.import_module(module_name)
            class_ = getattr(module, class_name)
            class_instance = class_()
            if class_name not in STATELESS_CLASSES:
                class_initial_config = initial_config.get(class_name, {})
                # Deep copy the initial configuration to avoid mutation issues
                # @HuanzhiMao TODO: update multi turn initial config format for reusability
                # "WeatherCom": "./data/multi_turn_initial_state/weather_com.json",
                class_instance._load_scenario(
                    copy.deepcopy(class_initial_config), long_context=long_context
                )
            globals()[instance_name] = class_instance
        # This happens in subsequent turns
        else:
            class_instance = globals()[instance_name]

        involved_instances[class_name] = class_instance

        # Retrieve all method names and map them to the instance
        for method_name, method in inspect.getmembers(
            class_instance, predicate=inspect.ismethod
        ):
            # Skip private methods
            if method_name.startswith("_"):
                continue
            class_method_name_mapping[method_name] = instance_name

    # Apply failure-injection patches once, right after instances are first created.
    if failure_injection and newly_created:
        _apply_failure_injections(involved_instances, failure_injection)

    execution_results = []
    for func_call in func_call_list:
        # Add the instance name to the method calls
        func_call = _process_method_calls(func_call, class_method_name_mapping)

        # Evaluate the function call
        try:
            # We need to make a copy here because otherwise the `eval(func_call)` would error.
            func_call_copy = func_call
            # Before calling `eval`, we need to make sure that the function call is safe
            # We do so by checking if the function is `kill` or `exit`, etc.
            # Extract the function name first
            if "(" in func_call_copy:
                func_call_copy = func_call_copy.split("(")[0]
            # Situation where the function call is a method call
            if "." in func_call_copy:
                func_call_copy = func_call_copy.split(".")[1]
            if func_call_copy.lower() in [
                "kill",
                "exit",
                "quit",
                "remove",
                "unlink",
                "popen",
                "run",
            ]:
                raise Exception(f"Function call {func_call_copy} is not allowed.")

            func_call_result = eval(func_call)
            result_type = ResultType.TEXT

            # Every result should be a dict with "result" and "result_type" keys
            if isinstance(func_call_result, ImageResult):
                result_type = ResultType.IMAGE
                func_call_result = func_call_result.to_dict()
            elif isinstance(func_call_result, dict):
                try:
                    func_call_result = json.dumps(func_call_result)
                except (TypeError, ValueError):
                    func_call_result = str(func_call_result)
            elif not isinstance(func_call_result, str):
                func_call_result = str(func_call_result)

            # @HuanzhiMao FIXME: update all related code for this new format
            execution_results.append(
                {
                    "result": func_call_result,
                    "result_type": result_type,
                }
            )
        except Exception as e:
            # raise e
            execution_results.append(
                {
                    "result": f"Error during execution: {str(e)}",
                    "result_type": ResultType.TEXT,
                }
            )

    return execution_results, involved_instances


def _sanitize_class_instance_name(name: str) -> str:
    # Replace any non-word char with underscore. \w includes Unicode letters/digits/underscore.
    name = re.sub(r"\W", "_", name, flags=re.UNICODE)

    # Identifiers can't start with a digit, and can't be empty
    if not name:
        raise ValueError(f"Invalid identifier for class instance name: {name}")
    if name[0].isdigit():
        name = "_" + name

    # Can't be a keyword
    if keyword.iskeyword(name):
        name += "_"

    return name


def is_empty_execute_response(input_list: list):
    if len(input_list) == 0:
        return True
    if len(input_list) == 1 and len(input_list[0]) == 0:
        return True
    return False


def _process_method_calls(function_call_string: str, instance_mapping: dict) -> str:
    """
    Prepends the instance name to the function name for each of the function name represented in the string, you will
    also be provided with the mapping of method name to instance name.

    Example input:
    ```
    f(x = g((1, 2), h(3)), y = (4), z = (5, 6))
    ```

    Example return:
    ```
    a.f(x=a.g((1, 2), a.h(3)), y=(4), z=(5, 6))
    ```

    Args:
        function_call_string (str): The function call string to parse.
        class_mapping (dict): A dictionary mapping method names to instance names.

    Returns:
        str: The parsed function call string with instance names prepended to method names.
    """

    def replace_function(match):
        func_name = match.group(1)
        if func_name in instance_mapping:
            return f"{instance_mapping[func_name]}.{func_name}"
        return func_name

    # Regular expression to match function names
    pattern = r"\b([a-zA-Z_]\w*)\s*(?=\()"

    # Replace function names with their class-prepended versions
    processed_string = re.sub(pattern, replace_function, function_call_string)

    return processed_string
