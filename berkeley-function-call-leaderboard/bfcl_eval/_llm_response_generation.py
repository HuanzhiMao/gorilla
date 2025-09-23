import argparse
import multiprocessing as mp
import os
import shutil
import traceback
from collections import defaultdict, deque
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait, Future
from copy import deepcopy

from bfcl_eval.constants.eval_config import (
    PROJECT_ROOT,
    RESULT_PATH,
    TEST_IDS_TO_GENERATE_PATH,
)
from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING
from bfcl_eval.eval_checker.eval_runner_helper import load_file
from bfcl_eval.model_handler.model_style import ModelStyle
from bfcl_eval.utils import *
from tqdm import tqdm


def get_args():
    parser = argparse.ArgumentParser()
    # Refer to model_choice for supported models.
    parser.add_argument("--model", type=str, default="gorilla-openfunctions-v2", nargs="+")
    # Refer to test_categories for supported categories.
    parser.add_argument("--test-category", type=str, default="all", nargs="+")

    # Parameters for the model that you want to test.
    parser.add_argument("--temperature", type=float, default=0.001)
    parser.add_argument("--include-input-log", action="store_true", default=False)
    parser.add_argument("--exclude-state-log", action="store_true", default=False)
    parser.add_argument("--num-threads", default=1, type=int)
    parser.add_argument("--num-gpus", default=8, type=int)
    parser.add_argument("--backend", default="vllm", type=str, choices=["vllm", "sglang"])
    parser.add_argument("--gpu-memory-utilization", default=0.9, type=float)
    parser.add_argument("--result-dir", default=None, type=str)
    parser.add_argument("--run-ids", action="store_true", default=False)
    parser.add_argument("--allow-overwrite", "-o", action="store_true", default=False)
    parser.add_argument(
        "--use-audio-input",
        action="store_true",
        default=False,
        help="Use audio input for the model. This is only supported for models that support native audio input.",
    )
    # Add the new skip_vllm argument
    parser.add_argument(
        "--skip-server-setup",
        action="store_true",
        default=False,
        help="Skip vLLM/SGLang server setup and use existing endpoint specified by the VLLM_ENDPOINT and VLLM_PORT environment variables.",
    )
    # Optional local model path
    parser.add_argument(
        "--local-model-path",
        type=str,
        default=None,
        help="Specify the path to a local directory containing the model's config/tokenizer/weights for fully offline inference. Use this only if the model weights are stored in a location other than the default HF_HOME directory.",
    )
    args = parser.parse_args()

    return args


def build_handler(model_name, temperature):
    config = MODEL_CONFIG_MAPPING[model_name]
    handler = config.model_handler(model_name, temperature)
    # Propagate config flags to the handler instance
    handler.is_fc_model = config.is_fc_model
    handler.supports_audio_input = config.supports_audio_input
    return handler


def get_involved_test_entries(test_category_args, run_ids, use_audio_input):
    all_test_categories, all_test_entries_involved = [], []
    if run_ids:
        all_test_categories, all_test_entries_involved = load_test_entries_from_id_file(
            TEST_IDS_TO_GENERATE_PATH
        )

    else:
        all_test_categories = parse_test_category_argument(test_category_args)
        for test_category in all_test_categories:
            all_test_entries_involved.extend(
                load_dataset_entry(test_category, use_audio_input=use_audio_input)
            )

    return (
        all_test_categories,
        all_test_entries_involved,
    )


def collect_test_cases(args, model_name, all_test_categories, all_test_entries_involved):
    model_name_dir = model_name.replace("/", "_")
    model_result_dir = args.result_dir / model_name_dir

    existing_result = []
    for test_category in all_test_categories:

        # TODO: Simplify the handling of memory prerequisite entries/categories
        result_file_paths = [
            model_result_dir
            / get_general_category(test_category)
            / get_file_name_by_category(test_category, is_result_file=True)
        ]
        if is_memory(test_category):
            # Memory test cases have the pre-requisite entries in a separate file
            result_file_paths.append(
                model_result_dir
                / get_general_category(test_category)
                / get_file_name_by_category(f"{test_category}_prereq", is_result_file=True)
            )

        for file_path in result_file_paths:
            if file_path.exists():
                # Not allowing overwrite, we will load the existing results
                if not args.allow_overwrite:
                    existing_result.extend(load_file(file_path))
                # Allow overwrite and not running specific test ids, we will delete the existing result file before generating new results
                elif not args.run_ids:
                    file_path.unlink()
                # Allow overwrite and running specific test ids, we will do nothing here
                else:
                    pass

        if is_memory(test_category):
            # We also need to special handle the pre-requisite entries and the snapshot result for memory test cases
            snapshot_folder = model_result_dir / "memory_snapshot" / test_category
            if snapshot_folder.exists():
                if not args.allow_overwrite:
                    pass
                elif not args.run_ids:
                    shutil.rmtree(snapshot_folder)
                else:
                    # TODO: If running id and id involes prereq entries, we should just delete those snapshot files
                    # It's not implemented yet, but it won't affect the accuracy, as those files will be overwritten anyway (assume generation success)
                    pass

        existing_ids = [entry["id"] for entry in existing_result]

    test_cases_to_generate = [
        test_case
        for test_case in all_test_entries_involved
        if test_case["id"] not in existing_ids
    ]

    test_cases_to_generate = clean_up_memory_prereq_entries(test_cases_to_generate)
    # TODO: Should we move these to the load_dataset_entry function?
    test_cases_to_generate = populate_initial_settings_for_memory_test_cases(
        test_cases_to_generate, model_result_dir
    )
    test_cases_to_generate = populate_initial_settings_for_web_search_test_cases(
        test_cases_to_generate
    )

    return sorted(test_cases_to_generate, key=sort_key)


def multi_threaded_inference(handler, test_case, include_input_log, exclude_state_log):

    assert type(test_case["function"]) is list

    try:
        result, metadata = handler.inference(
            deepcopy(test_case), include_input_log, exclude_state_log
        )
    except Exception as e:
        # This is usually the case when the model getting stuck on one particular test case.
        # For example, timeout error or FC model returning invalid JSON response.
        # Since temperature is already set to 0.001, retrying the same test case will not help.
        # So we continue the generation process and record the error message as the model response
        error_block = (
            "-" * 100
            + "\n❗️❗️ Error occurred during inference. Continuing to next test case.\n"
            + f"❗️❗️ Test case ID: {test_case['id']}, Error: {str(e)}\n"
            + traceback.format_exc(limit=10)
            + "-" * 100
        )
        print(error_block)

        result = f"Error during inference: {str(e)}"
        metadata = {"traceback": traceback.format_exc()}

    result_to_write = {
        "id": test_case["id"],
        "result": result,
        **metadata,
    }

    return result_to_write


def generate_results(args, model_name, test_cases_total):
    update_mode = args.allow_overwrite
    handler = build_handler(model_name, args.temperature)

    if handler.model_style == ModelStyle.OSSMODEL:
        # batch_inference will handle the writing of results
        handler.batch_inference(
            test_entries=test_cases_total,
            num_gpus=args.num_gpus,
            gpu_memory_utilization=args.gpu_memory_utilization,
            backend=args.backend,
            skip_server_setup=args.skip_server_setup,
            local_model_path=args.local_model_path,
            include_input_log=args.include_input_log,
            exclude_state_log=args.exclude_state_log,
            result_dir=args.result_dir,
            update_mode=update_mode,
        )
        return

    # ───── dependency bookkeeping ──────────────────────────────
    dependencies = {
        test_case["id"]: set(test_case.get("depends_on", []))
        for test_case in test_cases_total
    }
    children_of = defaultdict(list)
    for test_case in test_cases_total:
        for dependency_id in test_case.get("depends_on", []):
            children_of[dependency_id].append(test_case["id"])

    id_to_test_case = {test_case["id"]: test_case for test_case in test_cases_total}

    ready_queue = deque(
        [
            test_case_id
            for test_case_id, dependency_ids in dependencies.items()
            if not dependency_ids
        ]
    )
    in_flight: dict[Future, str] = {}  # future -> test_case_id
    completed = set()

    with ThreadPoolExecutor(max_workers=args.num_threads) as pool, tqdm(
        total=len(test_cases_total), desc=f"Generating results for {model_name}"
    ) as pbar:

        # seed initial ready tasks
        while ready_queue and len(in_flight) < args.num_threads:
            test_case_id = ready_queue.popleft()
            test_case = id_to_test_case[test_case_id]
            future = pool.submit(
                multi_threaded_inference,
                handler,
                test_case,
                args.include_input_log,
                args.exclude_state_log,
            )
            in_flight[future] = test_case_id

        # main scheduler loop
        while in_flight:
            done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for future in done:
                test_case_id = in_flight.pop(future)
                result_dict = future.result()
                handler.write(
                    result_dict, result_dir=args.result_dir, update_mode=args.run_ids
                )
                pbar.update()
                completed.add(test_case_id)

                # unlock children
                for child_id in children_of[test_case_id]:
                    dependencies[child_id].discard(test_case_id)
                    if not dependencies[child_id]:
                        ready_queue.append(child_id)

            # refill the pool up to max_workers
            while ready_queue and len(in_flight) < args.num_threads:
                test_case_id = ready_queue.popleft()
                test_case = id_to_test_case[test_case_id]
                future = pool.submit(
                    multi_threaded_inference,
                    handler,
                    test_case,
                    args.include_input_log,
                    args.exclude_state_log,
                )
                in_flight[future] = test_case_id


def main(args):

    # Note: The following environment variables are needed for the memory vector store implementation
    # Otherwise you get segfault or huggingface tokenizer warnings
    # disable HuggingFace tokenizers’ thread pool
    os.environ["TOKENIZERS_PARALLELISM"] = "false"
    # limit all OpenMP/MKL threads to 1
    os.environ["OMP_NUM_THREADS"] = "1"
    os.environ["MKL_NUM_THREADS"] = "1"
    # use spawn method for multiprocessing
    mp.set_start_method("spawn", force=True)

    if type(args.model) is not list:
        args.model = [args.model]
    if type(args.test_category) is not list:
        args.test_category = [args.test_category]

    (
        all_test_categories,
        all_test_entries_involved,
    ) = get_involved_test_entries(args.test_category, args.run_ids, args.use_audio_input)

    for model_name in args.model:
        if model_name not in MODEL_CONFIG_MAPPING:
            raise ValueError(
                f"Unknown model_name '{model_name}'.\n"
                "• For officially supported models, please refer to `SUPPORTED_MODELS.md`.\n"
                "• For running new models, please refer to `README.md` and `CONTRIBUTING.md`."
            )
        if (
            args.use_audio_input
            and not MODEL_CONFIG_MAPPING[model_name].supports_audio_input
        ):
            raise ValueError(f"Model {model_name} does not support native audio input.")

        if args.use_audio_input and not model_name.startswith("audio:"):
            raise ValueError(
                f"Model {model_name} should not be used with the --use-audio-input flag. Please use the `audio:` prefix for models that support native audio input. For example, use `audio:gemini-2.5-pro-Audio-FC` instead of `gemini-2.5-pro-Audio-FC`."
            )

    print(f"Generating results for {args.model}")
    if args.run_ids:
        print("Running specific test cases. Ignoring `--test-category` argument.")
    else:
        print(f"Running full test cases for categories: {all_test_categories}.")

    if args.result_dir is not None:
        args.result_dir = PROJECT_ROOT / args.result_dir
    else:
        args.result_dir = RESULT_PATH

    for model_name in args.model:
        test_cases_total = collect_test_cases(
            args,
            model_name,
            all_test_categories,
            all_test_entries_involved,
        )

        if len(test_cases_total) == 0:
            print(
                f"All selected test cases have been previously generated for {model_name}. No new test cases to generate."
            )
        else:
            # print(test_cases_total[:1])
            generate_results(args, model_name, test_cases_total)
            # FIXME: Sort the result files by id at the end
