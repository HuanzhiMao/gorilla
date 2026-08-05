import json
from copy import deepcopy
from typing import TYPE_CHECKING, Any
from tqdm import tqdm
from bfcl_eval.constants.default_prompts import (
    DEFAULT_USER_PROMPT_FOR_ADDITIONAL_FUNCTION_FC,
)
import traceback
from bfcl_eval.constants.enums import ModelStyle, ResultType, ReturnFormat
from bfcl_eval.constants.eval_config import (
    MAXIMUM_CLARIFICATION_LIMIT,
    MAXIMUM_STEP_LIMIT,
    RESULT_PATH,
)
from bfcl_eval.utils import could_allow_clarification, get_category_modality
from bfcl_eval.constants.executable_backend_config import (
    END_SESSION_AFTER_EVAL_CLASSES,
    OMIT_STATE_INFO_CLASSES,
    STATELESS_CLASSES,
    UPDATED_TOOL_LIST_CLASSES,
)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import (
    execute_multi_turn_func_call,
    is_empty_execute_response,
)
from bfcl_eval.model_handler.utils import (
    add_memory_instruction_system_prompt,
    check_for_clarification,
    extract_clarification_context,
)
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.environment import HoldoutCondition
from bfcl_eval.schemas.message import Message, Role
from bfcl_eval.schemas.results import ModelResultEntry
from bfcl_eval.utils import *
from overrides import final

if TYPE_CHECKING:
    from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.memory_api_metaclass import (
        MemoryAPI,
    )


class BaseHandler:
    model_name: str
    registry_name: str
    temperature: float
    registry_dir_name: str
    model_name_underline_replaced: str
    model_style: ModelStyle

    # Capability flags: every subclass must explicitly declare these as class
    # attributes so handler authors are forced to consider each modality.
    #
    # They answer "can THIS HANDLER put that modality on the wire for its provider's
    # API", not "does the model understand it". The second question is per-model and
    # lives on `ModelConfig.supports_audio_input` / `supports_image_input` in
    # `constants/model_config.py`. A category runs only when both agree; see
    # `skip_rules` in `_llm_response_generation.py`.
    #
    # `can_handle_image_tool_response` may be True on a provider whose tool-result
    # message is text-only, as long as the handler delivers the image some other
    # documented way -- what matters is that the bytes reach the model.
    can_handle_audio_input: bool
    can_handle_image_input: bool
    can_handle_image_tool_response: bool

    _REQUIRED_CAPABILITY_FLAGS = (
        "can_handle_audio_input",
        "can_handle_image_input",
        "can_handle_image_tool_response",
    )

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        missing = [
            attr for attr in BaseHandler._REQUIRED_CAPABILITY_FLAGS if attr not in vars(cls)
        ]
        if missing:
            raise TypeError(
                f"{cls.__name__} must explicitly declare: {', '.join(missing)}"
            )
        # Delivering an image tool result means getting an image to the model, whether
        # the provider has a field for it or an emulating user message is needed. Every
        # route ends in a rendered image, so claiming one without the other describes
        # nothing a handler can actually do -- and the emulated route builds its own
        # user message, which never passes back through the modality backstop.
        if cls.can_handle_image_tool_response and not cls.can_handle_image_input:
            raise TypeError(
                f"{cls.__name__} declares can_handle_image_tool_response without "
                f"can_handle_image_input: an image tool result has to reach the model "
                f"as an image either way."
            )

    def __init__(
        self, model_name, temperature, registry_name, **kwargs
    ) -> None:
        """
        Args:
            model_name: The name of the model as used in the vendor API or on Hugging Face.
            temperature: The temperature of the model.
            registry_name: The name of the model as used internally in BFCL, used for result directory naming.
            **kwargs: Additional attributes passed via kwargs.
        """
        self.model_name = model_name
        self.registry_name = registry_name

        # Replace the dash and dot with underscore for valid variable name
        self.model_name_underline_replaced = (
            model_name.replace("/", "_").replace("-", "_").replace(".", "_")
        )
        # The directory name for the model
        # Look up the pre-computed sanitized name from model_config as the single source of truth.
        # Import here to avoid circular imports (model_config imports handler classes).
        from bfcl_eval.constants.model_config import REGISTRY_TO_DIR_NAME

        self.registry_dir_name = REGISTRY_TO_DIR_NAME[registry_name]
        self.temperature = temperature

        # Set any additional attributes passed via kwargs
        for _key, _value in kwargs.items():
            setattr(self, _key, _value)

    @final
    def _reject_unrenderable_modalities(self, messages: list[Message]) -> None:
        """Refuse a turn carrying a modality this handler cannot put on the wire.

        The runner already skips categories a model/handler pair cannot take, so this
        is a backstop rather than a routine check. It exists because the alternative
        failure is invisible: every handler builds its payload field by field, so an
        unhandled image or audio clip is simply *not copied* and the model is scored on
        a question it was never shown.
        """
        for message in messages:
            if message.has_audio and not self.can_handle_audio_input:
                raise ValueError(
                    f"{type(self).__name__} cannot send audio input, but a "
                    f"{message.role.value} message carries an audio clip. Gate this "
                    f"category out (`supports_audio_input` in model_config.py) rather "
                    f"than letting the handler drop it."
                )
            if message.has_image and not self.can_handle_image_input:
                raise ValueError(
                    f"{type(self).__name__} cannot send image input, but a "
                    f"{message.role.value} message carries {len(message.images)} "
                    f"image(s). Gate this category out (`supports_image_input` in "
                    f"model_config.py) rather than letting the handler drop them."
                )

    @final
    def _reject_unrenderable_execution_results(
        self, execution_results: list[dict]
    ) -> None:
        """Same backstop for images a tool returned."""
        if self.can_handle_image_tool_response:
            return
        if any(result["result_type"] == ResultType.IMAGE for result in execution_results):
            raise ValueError(
                f"{type(self).__name__} cannot deliver an image tool result, but a "
                f"tool returned one. Categories whose tools return images "
                f"(`tools_return_images` on the category spec) must be gated out for "
                f"this model."
            )

    def inference(
        self,
        test_entry: TestEntry,
        include_input_log: bool,
        exclude_state_log: bool,
    ):
        # This method is used to retrive model response for each model.
        # Only function-calling (FC) inference is supported; the prompting
        # (chat-based tool calling) pathway has been retired.
        return self.inference_multi_turn_FC(
            test_entry, include_input_log, exclude_state_log
        )

    @final
    def inference_multi_turn_FC(
        self,
        test_entry: TestEntry,
        include_input_log: bool,
        exclude_state_log: bool,
    ) -> tuple[list[list], dict]:
        environment = test_entry.environment
        initial_config: dict = environment.initial_config
        involved_classes: list = environment.involved_classes
        test_entry_id: str = test_entry.id
        category = test_entry.category
        test_category: str = category.value
        max_step_limit = MAXIMUM_STEP_LIMIT[category.modality]
        # Only for audio tasks, we allow the model to ask for clarification.
        category_allow_clarification: bool = category.allows_clarification

        # This is only for the miss function category
        # Supports conditions: "after_n_turns" and "after_n_invoke"
        missed_classes_rules = environment.holdout_rules
        failure_injection = (
            [injection.to_dict() for injection in environment.failure_injections] or None
        )

        total_input_token_count: list[list[float]] = []
        total_output_token_count: list[list[float]] = []
        total_latency: list[list[float]] = []
        all_model_response: list[list] = (
            []
        )  # The model response that will be used for later evaluation
        all_inference_log: list[list[dict]] = (
            []
        )  # The debugging log for human to understand
        force_quit = False  # Whether the model has been forced to quit. If True, this whole entry will be failed.

        all_reasoning_content: list[list] = []

        # Execute no function call, but just to get a reference to all the instances to get the initial state for logging purpose
        # Also applies failure_injection patches at instance creation time (turn 0).
        _, involved_instances = execute_multi_turn_func_call(
            [],
            initial_config,
            involved_classes,
            self.model_name_underline_replaced,
            test_entry_id,
            long_context=category.long_context,
            is_evaL_run=False,
            failure_injection=failure_injection,
        )

        if failure_injection:
            all_inference_log.append(
                [
                    {
                        "role": "handler_log",
                        "content": {
                            "action": "failure_injection_applied",
                            "patches": failure_injection,
                        },
                    }
                ]
            )

        if category.is_memory:
            assert (
                len(involved_instances) == 1
            ), "Memory category should only involve one class."

            memory_instance: "MemoryAPI" = list(involved_instances.values())[0]
            test_entry.conversation = add_memory_instruction_system_prompt(
                test_entry.conversation,
                test_category,
                test_entry.scenario,
                memory_instance,
            )

        if not exclude_state_log:
            state_log = []
            for class_name, class_instance in involved_instances.items():
                if class_name in STATELESS_CLASSES or class_name in OMIT_STATE_INFO_CLASSES:
                    continue
                # Avoid modification in future turns
                class_instance = deepcopy(class_instance)
                state_log.append(
                    {
                        "role": "state_info",
                        "class_name": class_name,
                        "content": {
                            key: value
                            for key, value in vars(class_instance).items()
                            if not key.startswith("_")
                        },
                    }
                )
            if len(state_log) > 0:
                all_inference_log.append(state_log)

        inference_data: dict = {}
        inference_data = self._pre_query_processing_FC(inference_data, test_entry)
        inference_data = self._compile_tools(inference_data, test_entry)

        all_multi_turn_messages = test_entry.conversation
        for turn_idx, current_turn_message in enumerate(all_multi_turn_messages):
            current_turn_message: list[Message]

            if any(
                class_name in UPDATED_TOOL_LIST_CLASSES for class_name in involved_classes
            ):
                test_entry = update_available_tool_list_in_test_case(
                    test_entry, involved_instances
                )
                self._compile_tools(inference_data, test_entry)

            released_holdout_log = []
            for holdout_rule in missed_classes_rules:
                if holdout_rule.is_triggered(turn_index=turn_idx):
                    released_holdout_log.append({
                        "released_functions": holdout_rule.holdout_function_names,
                        "condition": holdout_rule.condition.value,
                        "triggered_turn": turn_idx,
                    })
                    test_entry.release_holdout(holdout_rule)
                    inference_data = self._compile_tools(inference_data, test_entry)
                    assert (
                        len(current_turn_message) == 0
                    ), "Holdout turn should not have user message."
                    # TODO: Move this to before pre_query_processing_FC.
                    # Shouldn't be happening in the inference loop.
                    current_turn_message = [
                        Message(
                            role=Role.USER,
                            content=DEFAULT_USER_PROMPT_FOR_ADDITIONAL_FUNCTION_FC,
                        )
                    ]

            # Binary payloads are stripped from the log rather than deep-copied out of
            # it. Unconditionally: keying this on `contains_vision_input` left the mp3
            # bytes of a true_audio entry to be stringified into every result file, and
            # a log has no use for the bytes in any modality.
            current_turn_message_for_logging = [
                message.to_dict(redact_binary=True) for message in current_turn_message
            ]

            current_turn_response = []
            current_turn_inference_log: list[dict] = {
                "begin_of_turn_query": current_turn_message_for_logging
            }
            if released_holdout_log:
                current_turn_inference_log["released_holdout_functions"] = released_holdout_log
            current_turn_input_token_count: list[float] = []
            current_turn_output_token_count: list[float] = []
            current_turn_latency: list[float] = []
            current_turn_reasoning_content = []

            self._reject_unrenderable_modalities(current_turn_message)

            if turn_idx == 0:
                inference_data = self.add_first_turn_message_FC(
                    inference_data, current_turn_message
                )
            else:
                inference_data = self._add_next_turn_user_message_FC(
                    inference_data, current_turn_message
                )

            step_count = 0
            clarification_count = 0

            while True:
                # @HuanzhiMao FIXME: check if allow clarification
                tqdm.write(
                    f"{'-' * 100}\nID: {test_entry_id}, Turn: {turn_idx}, Step: {step_count}, Clarification Count: {clarification_count}"
                )
                current_step_inference_log: list[dict] = []
                # Add to the current_turn_inference_log at beginning of each step so that we don't need to bother dealing with the break statements
                current_turn_inference_log[f"step_{step_count}"] = (
                    current_step_inference_log
                )

                api_response, query_latency = self._query_FC(inference_data)

                # This part of logging is disabled by default because it is too verbose and will make the result file extremely large
                # It is only useful to see if the inference pipeline is working as expected (eg, does it convert all the inputs correctly)
                if include_input_log:
                    current_step_inference_log.append(
                        {
                            "role": "inference_input",
                            "content": inference_data.get("inference_input_log", ""),
                        }
                    )

                # Try parsing the model response
                model_response_data = self._parse_query_response_FC(api_response)
                model_responses = model_response_data["model_responses"]

                # Add the assistant message to the chat history
                inference_data = self._add_assistant_message_FC(
                    inference_data, model_response_data
                )

                # Process the metadata
                current_turn_input_token_count.append(model_response_data["input_token"])
                current_turn_output_token_count.append(model_response_data["output_token"])
                current_turn_latency.append(query_latency)

                current_turn_response.append(model_responses)

                reasoning_content = model_response_data.get("reasoning_content", "")
                current_turn_reasoning_content.append(reasoning_content)

                log_entry = {
                    "role": "assistant",
                    "content": model_responses,
                }
                if reasoning_content:
                    log_entry["reasoning_content"] = reasoning_content

                current_step_inference_log.append(log_entry)

                step_count += 1

                # For single-turn entries that don't allow clarification,
                # we don't need to decode or execute function calls.
                # The eval will handle decoding separately.
                if (
                    not category.contains_multi_step_interaction
                    and not category_allow_clarification
                ):
                    break

                # Try decoding the model response into executable function calls
                decoded_model_responses = None
                has_function_calls = False

                try:
                    decoded_model_responses = self.decode_execute(
                        model_responses, has_tool_call_tag=False
                    )
                    current_step_inference_log.append(
                        {
                            "role": "handler_log",
                            "content": "Successfully decoded model response.",
                            "model_response_decoded": decoded_model_responses,
                        }
                    )
                    # @HuanzhiMao double check if this is necessary

                    if is_empty_execute_response(decoded_model_responses):
                        current_step_inference_log.append(
                            {
                                "role": "handler_log",
                                "content": "Empty response from the model.",
                                "model_response_decoded": decoded_model_responses,
                            }
                        )
                    else:
                        has_function_calls = True
                        model_responses = decoded_model_responses

                except Exception as e:
                    # print("🔍 Error decoding the model response.", traceback.format_exc())
                    current_step_inference_log.append(
                        {
                            "role": "handler_log",
                            "content": "Error decoding the model response.",
                            "model_response": model_responses,
                            "error": str(e),
                        }
                    )

                # Path 1: Model produced function calls → execute them
                if has_function_calls:
                    # If it's a single-turn entry, we don't need to execute the function calls. The generation stops here.
                    if not category.contains_multi_step_interaction:
                        break

                    # Obtain the execution results
                    execution_results, involved_instances = execute_multi_turn_func_call(
                        decoded_model_responses,
                        initial_config,
                        involved_classes,
                        self.model_name_underline_replaced,
                        test_entry_id,
                        long_context=category.long_context,
                        is_evaL_run=False,
                    )

                    # Add the execution results to the chat history for the next turn
                    self._reject_unrenderable_execution_results(execution_results)
                    inference_data = self._add_execution_results_FC(
                        inference_data, execution_results, model_response_data
                    )

                    for execution_result in execution_results:
                        # @HuanzhiMao FIXME: Update for prompting method as well.
                        if execution_result["result_type"] == "image":
                            current_step_inference_log.append(
                                {
                                    "role": "tool",
                                    "content": "This is an image result. Removed for logging purpose.",
                                }
                            )
                        else:
                            current_step_inference_log.append(
                                {
                                    "role": "tool",
                                    "content": execution_result["result"],
                                }
                            )

                    # Check if holdout functions should be released after this invocation
                    for holdout_rule in missed_classes_rules:
                        if holdout_rule.released:
                            continue
                        if holdout_rule.condition is HoldoutCondition.AFTER_N_INVOKE:
                            # target_function may be "ClassName.func_name"; decoded responses use bare func names
                            target_func = holdout_rule.bare_target_function
                            for func_call in decoded_model_responses:
                                if isinstance(func_call, str) and func_call.startswith(target_func + "("):
                                    if holdout_rule.record_invocation():
                                        current_step_inference_log.append(
                                            {
                                                "role": "handler_log",
                                                "content": {
                                                    "action": "missed_classes_holdout_released",
                                                    "released_functions": holdout_rule.holdout_function_names,
                                                    "condition": holdout_rule.condition.value,
                                                    "target_function": holdout_rule.target_function,
                                                    "invoke_count": holdout_rule.invocations,
                                                    "required_invocations": holdout_rule.invoke_threshold,
                                                },
                                            }
                                        )
                                        test_entry.release_holdout(holdout_rule)
                                        inference_data = self._compile_tools(inference_data, test_entry)
                                    break

                    # If the model has taken too many steps, we force it to quit.
                    if step_count > max_step_limit:
                        force_quit = True
                        current_step_inference_log.append(
                            {
                                "role": "handler_log",
                                "content": f"Model has been forced to quit after {max_step_limit} steps.",
                            }
                        )
                        break

                    continue

                # Path 2: No function calls → if model is allowed to ask clarification, check if model is asking a valid clarification.
                elif category_allow_clarification:
                    (
                        allowed_clarifications,
                        original_user_request,
                        last_user_message_asr_output,
                    ) = extract_clarification_context(current_turn_message)

                    is_clarification, clarification_content = check_for_clarification(
                        model_response=model_responses,
                        allowed_clarifications=allowed_clarifications,
                        original_user_request=original_user_request,
                        asr_output=last_user_message_asr_output,
                    )

                    if is_clarification:
                        clarification_count += 1
                        if clarification_count > MAXIMUM_CLARIFICATION_LIMIT:
                            force_quit = True
                            current_step_inference_log.append(
                                {
                                    "role": "handler_log",
                                    "content": f"Model has been forced to quit after {MAXIMUM_CLARIFICATION_LIMIT} clarifications. Way too many clarifications than needed.",
                                }
                            )
                            break

                        # A clarification round costs a query like any other step, so
                        # it has to answer to the step limit too. This branch used to
                        # skip the check and was bounded only by the clarification
                        # count, which let a turn spend MAXIMUM_CLARIFICATION_LIMIT
                        # queries beyond a budget that is supposed to be the ceiling.
                        if step_count > max_step_limit:
                            force_quit = True
                            current_step_inference_log.append(
                                {
                                    "role": "handler_log",
                                    "content": f"Model has been forced to quit after {max_step_limit} steps.",
                                }
                            )
                            break

                        # Handlers consume `Message` objects, never raw dicts -- the
                        # simulated clarification answer has to be one too.
                        inference_data = self._add_next_turn_user_message_FC(
                            inference_data,
                            [Message(role=Role.USER, content=clarification_content)],
                        )
                        current_step_inference_log.append(
                            {
                                "role": "handler_log:answer_clarification",
                                "content": "Model asked a clarification matching an allowed topic. Responding and continuing the current turn's step loop.",
                                "model_response": model_responses,
                                "allowed_clarifications": allowed_clarifications,
                                "clarification_message": clarification_content,
                            }
                        )
                        continue
                    else:
                        current_step_inference_log.append(
                            {
                                "role": "handler_log:no_clarification",
                                "content": "Clarification is enabled, but model response did not match any allowed clarification topic. Proceed to next turn.",
                                "model_response": model_responses,
                                "allowed_clarifications": allowed_clarifications,
                            }
                        )

                    break

                # Path 3: No function calls, not allowed to ask clarification → done with this turn
                else:
                    break

            # Add to the total list
            all_model_response.append(current_turn_response)
            all_inference_log.append(current_turn_inference_log)
            all_reasoning_content.append(current_turn_reasoning_content)
            total_input_token_count.append(current_turn_input_token_count)
            total_output_token_count.append(current_turn_output_token_count)
            total_latency.append(current_turn_latency)

            if not exclude_state_log:
                state_log = []
                for class_name, class_instance in involved_instances.items():
                    if (
                        class_name in STATELESS_CLASSES
                        or class_name in OMIT_STATE_INFO_CLASSES
                    ):
                        continue
                    # Avoid modification in future turns
                    class_instance = deepcopy(class_instance)
                    state_log.append(
                        {
                            "role": "state_info",
                            "class_name": class_name,
                            "content": {
                                key: value
                                for key, value in vars(class_instance).items()
                                if not key.startswith("_")
                            },
                        }
                    )
                if len(state_log) > 0:
                    all_inference_log.append(state_log)

            if force_quit:
                break

        # Special handling for the memory category
        # Need to flush the memory to local file at the end of the conversation
        if category.is_memory_prereq:
            assert (
                len(involved_instances) == 1
            ), "Memory category should only involve one class."
            memory_instance: "MemoryAPI" = list(involved_instances.values())[0]
            memory_instance._flush_memory_to_local_file()

        # Clean up, close sessions if needed.
        for class_name, class_instance in involved_instances.items():
            if class_name in END_SESSION_AFTER_EVAL_CLASSES:
                class_instance._end_session()

        metadata = {
            "input_token_count": total_input_token_count,
            "output_token_count": total_output_token_count,
            "latency": total_latency,
        }

        if category.contains_multi_step_interaction:
            metadata["inference_log"] = all_inference_log

        if not all(
            all(content == "" for content in single_turn_reasoning_content)
            for single_turn_reasoning_content in all_reasoning_content
        ):
            metadata["reasoning_content"] = all_reasoning_content

        return all_model_response, metadata

    @final
    def inference_single_turn_FC(
        self, test_entry: TestEntry, include_input_log: bool
    ) -> tuple[any, dict]:
        inference_data: dict = {}
        inference_data = self._pre_query_processing_FC(inference_data, test_entry)
        inference_data = self._compile_tools(inference_data, test_entry)
        self._reject_unrenderable_modalities(test_entry.conversation[0])
        inference_data = self.add_first_turn_message_FC(
            inference_data, test_entry.conversation[0]
        )

        api_response, query_latency = self._query_FC(inference_data)

        # Try parsing the model response
        model_response_data = self._parse_query_response_FC(api_response)

        # Process the metadata
        metadata = {}
        if include_input_log:
            metadata["inference_log"] = [
                {
                    "role": "inference_input",
                    "content": inference_data.get("inference_input_log", ""),
                }
            ]
        metadata["input_token_count"] = model_response_data["input_token"]
        metadata["output_token_count"] = model_response_data["output_token"]
        metadata["latency"] = query_latency

        if (
            "reasoning_content" in model_response_data
            and model_response_data["reasoning_content"] != ""
        ):
            metadata["reasoning_content"] = model_response_data["reasoning_content"]

        return model_response_data["model_responses"], metadata

    def decode_ast(self, result, language: ReturnFormat, has_tool_call_tag: bool):
        """
        This method takes raw model output (from `_parse_query_response_xxx`) and convert it to standard AST checker input.
        """
        raise NotImplementedError

    def decode_execute(self, result, has_tool_call_tag: bool):
        """
        This method takes raw model output (from `_parse_query_response_xxx`) and convert it to standard execute checker input.
        """
        raise NotImplementedError

    @final
    def write(self, result, result_dir, update_mode=False):
        """Append (or update) result entries in the per-category result files.

        Accepts `ModelResultEntry` objects, or the plain dicts they serialize to.
        """
        # Use the internal registry name to decide the result directory to avoid
        # collisions between different variants that share the same API model name.
        model_result_dir = result_dir / self.registry_dir_name

        if isinstance(result, (dict, ModelResultEntry)):
            result = [result]

        # Collect and format each entry for JSON compatibility
        entries_to_write = [
            make_json_serializable(
                entry.to_dict() if isinstance(entry, ModelResultEntry) else entry
            )
            for entry in result
        ]

        # Group entries by their `test_category` for efficient file handling
        file_entries = {}
        for entry in entries_to_write:
            test_category = extract_test_category_from_id(entry["id"])
            # Determine the high-level grouping folder (text, vision, true_audio, text_audio)
            group_dir_name = get_directory_structure_by_id(entry["id"])
            group_dir_path = model_result_dir / group_dir_name
            group_dir_path.mkdir(parents=True, exist_ok=True)

            base_category = get_base_category(test_category)
            file_path = group_dir_path / f"{base_category}_result.json"
            file_entries.setdefault(file_path, []).append(entry)

        for file_path, entries in file_entries.items():
            if update_mode:
                # Load existing entries from the file
                existing_entries = {}
                if file_path.exists():
                    existing_entries = {
                        entry["id"]: entry for entry in load_file(file_path)
                    }

                # Update existing entries with new data
                for entry in entries:
                    existing_entries[entry["id"]] = entry

                # Sort entries by `id` and write them back to ensure order consistency
                sorted_entries = sorted(existing_entries.values(), key=sort_key)
                with open(file_path, "w") as f:
                    for entry in sorted_entries:
                        content = json.dumps(entry) + "\n"
                        f.write(content)
                        f.flush()

            else:
                # Normal mode: Append to the end of the file
                # Note: We will sort all the entries at the end of the generation pipeline to ensure the order is consistent
                entries.sort(key=sort_key)
                with open(file_path, "a") as f:
                    for entry in entries:
                        content = json.dumps(entry) + "\n"
                        f.write(content)
                        f.flush()

    #### FC methods ####

    def _query_FC(self, inference_data: dict):
        """
        Call the model API in FC mode to get the response.
        Return the response object that can be used to feed into the `_parse_query_response_FC` method.
        """
        raise NotImplementedError

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: TestEntry) -> dict:
        """
        Preprocess the testset entry before sending it to the model.
        This might includes transforming the input user message into the format expected by the model, extract out the system prompt (if any), and any other necessary preprocessing steps. Those steps can also be done in the `add_first_turn_message_FC` and `_add_next_turn_user_message_FC` methods, but it's usually cleaner to do it here.
        The inference_data dict is updated in place and returned.

        Note: This method has different signature from its Prompting version.
        """
        raise NotImplementedError

    def _compile_tools(self, inference_data: dict, test_entry: TestEntry) -> dict:
        """
        [Only for FC mode]
        This method is used to prepare/compile the tools from the test entry and add them to the inference data to use for model query in FC mode.
        Function docs usually need to be transformed to the format expected by the model, done through the `convert_to_tool` function from `model_handler/utils.py`.
        The inference_data dict is updated in place and returned.
        """
        raise NotImplementedError

    def _parse_query_response_FC(self, api_response: Any) -> dict:
        """
        Parses the raw response from the model API to extract the result, input token count, and output token count.

        Args:
            api_response (any): The raw response from the model API.

        Returns:
            A dict containing the following elements:
                - model_responses (any): The parsed result that can be directly used as input to the decode method.
                - input_token (int): The number of tokens used in the input to the model.
                - output_token (int): The number of tokens generated by the model as output.
                - tool_call_ids (list[str]): The IDs of the tool calls that are generated by the model. Optional.
                - Any other metadata that is specific to the model.
        """
        raise NotImplementedError

    def add_first_turn_message_FC(
        self, inference_data: dict, first_turn_message: list[Message]
    ) -> dict:
        """
        Add the first turn message to the chat history, in the format that the model expects.

        Args:
            inference_data (dict): The inference data from previous processing steps.
            first_turn_message (list[Message]): The first turn message from the test entry. It has variable length. It might contain one or more of the following roles:
                - "system": The system message. This role will only appear at most once, at the beginning of the first turn. For most entry, this role will not appear.
                - "user": The user message.
                - "assistant": The assistant message. For most entry, this role will not appear.

        Returns:
            inference_data (dict): The updated inference data that will be send to `_query_FC` to call the model API.
        """
        raise NotImplementedError

    def _add_next_turn_user_message_FC(
        self, inference_data: dict, user_message: list[Message]
    ) -> dict:
        """
        [Only for multi-turn]
        Add next turn user message to the chat history for query.
        user_message is a list of 1 element, which is guaranteed to be a `user` role message.
        """
        raise NotImplementedError

    def _add_assistant_message_FC(
        self, inference_data: dict, model_response_data: dict
    ) -> dict:
        """
        Add assistant message to the chat history.
        """
        raise NotImplementedError

    def _add_execution_results_FC(
        self, inference_data: dict, execution_results: list[dict], model_response_data: dict
    ) -> dict:
        """
        Add the execution results to the chat history to prepare for the next turn of query.
        Some models may need to add additional information to the chat history, such as tool call IDs.
        """
        raise NotImplementedError
