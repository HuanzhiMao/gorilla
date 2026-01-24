import os
from re import S
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

import requests
from bfcl_eval.constants.eval_config import LOCAL_SERVER_PORT
from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from bfcl_eval.model_handler.utils import (
    default_decode_ast_prompting,
    default_decode_execute_prompting,
    system_prompt_pre_processing_chat_model,
)
from openai import OpenAI
from overrides import EnforceOverrides, final, override


class OSSHandler(OpenAICompletionsHandler, EnforceOverrides):
    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        is_fc_model,
        dtype="bfloat16",
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, is_fc_model, **kwargs)
        self.model_name_huggingface = model_name
        self.dtype = dtype
        self.tool_call_parser = None

        # Will be overridden in batch_inference method
        # Used to indicate where the tokenizer and config should be loaded from
        self.model_path_or_id = None

        # Read from env vars with fallbacks
        self.local_server_endpoint = os.getenv("LOCAL_SERVER_ENDPOINT", "localhost")
        self.local_server_port = os.getenv("LOCAL_SERVER_PORT", LOCAL_SERVER_PORT)

        # Support custom base_url and api_key for remote/local OpenAI-compatible deployments (e.g., vLLM)
        # Use REMOTE_OPENAI_* variables to avoid conflicts with main OPENAI_* variables
        self.base_url = os.getenv(
            "REMOTE_OPENAI_BASE_URL",
            f"http://{self.local_server_endpoint}:{self.local_server_port}/v1",
        )
        self.api_key = os.getenv("REMOTE_OPENAI_API_KEY", "EMPTY")
        self.client = OpenAI(base_url=self.base_url, api_key=self.api_key)

    def _build_extra_body(self) -> dict:
        extra_body = {}
        if hasattr(self, "stop_token_ids"):
            extra_body["stop_token_ids"] = self.stop_token_ids
        if hasattr(self, "skip_special_tokens"):
            extra_body["skip_special_tokens"] = self.skip_special_tokens
        return extra_body

    def _resolve_tool_call_parser(self) -> str | None:
        return os.getenv("VLLM_TOOL_CALL_PARSER", self.tool_call_parser)

    @override
    def _query_FC(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        tools = inference_data["tools"]
        inference_data["inference_input_log"] = {"message": repr(message), "tools": tools}

        kwargs = {
            "messages": message,
            "model": self.model_path_or_id,
            "temperature": self.temperature,
            "timeout": 72000,
        }

        if len(tools) > 0:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        extra_body = self._build_extra_body()
        if extra_body:
            kwargs["extra_body"] = extra_body

        return self.generate_with_backoff(**kwargs)

    @override
    def _query_prompting(self, inference_data: dict):
        inference_data["inference_input_log"] = {"message": repr(inference_data["message"])}

        kwargs = {
            "messages": inference_data["message"],
            "model": self.model_path_or_id,
            "temperature": self.temperature,
            "timeout": 72000,
        }
        extra_body = self._build_extra_body()
        if extra_body:
            kwargs["extra_body"] = extra_body

        return self.generate_with_backoff(**kwargs)

    @final
    def spin_up_local_server(
        self,
        num_gpus: int,
        gpu_memory_utilization: float,
        backend: str,
        skip_server_setup: bool,
        local_model_path: Optional[str],
        lora_modules: Optional[list[str]] = None,
        enable_lora: bool = False,
        max_lora_rank: Optional[int] = None,
    ):
        """
        Spin up a local server for the model.
        If the server is already running, skip the setup.
        """
        if local_model_path is not None:
            self.model_path_or_id = local_model_path
        else:
            self.model_path_or_id = self.model_name_huggingface

        self._server_process = process = None
        self._stdout_thread = stdout_thread = None
        self._stderr_thread = stderr_thread = None
        # Event to signal threads to stop; no need to see logs after server is ready
        # declare early so it always exists
        self._stop_event = threading.Event()
        try:
            if not skip_server_setup:
                if backend == "vllm":
                    tool_call_parser = None
                    if self.is_fc_model:
                        tool_call_parser = self._resolve_tool_call_parser()
                        if not tool_call_parser:
                            raise ValueError(
                                "Function calling models require a supported vLLM tool call parser. "
                                "Set VLLM_TOOL_CALL_PARSER or update the model handler."
                            )
                    process = subprocess.Popen(
                        [
                            "vllm",
                            "serve",
                            str(self.model_path_or_id),
                            "--port",
                            str(self.local_server_port),
                            "--dtype",
                            str(self.dtype),
                            "--tensor-parallel-size",
                            str(num_gpus),
                            "--gpu-memory-utilization",
                            str(gpu_memory_utilization),
                            "--trust-remote-code",
                        ]
                        + (
                            [
                                "--enable-auto-tool-choice",
                                "--tool-call-parser",
                                tool_call_parser,
                            ]
                            if tool_call_parser
                            else []
                        )
                        + (["--enable-lora"] if enable_lora else [])
                        + (
                            ["--max-lora-rank", str(max_lora_rank)]
                            if max_lora_rank is not None
                            else []
                        )
                        + (
                            sum(
                                [
                                    ["--lora-modules", lora_module]
                                    for lora_module in lora_modules
                                ],
                                [],
                            )
                            if lora_modules
                            else []
                        ),
                        stdout=subprocess.PIPE,  # Capture stdout
                        stderr=subprocess.PIPE,  # Capture stderr
                        text=True,  # To get the output as text instead of bytes
                    )
                else:
                    raise ValueError(f"Backend {backend} is not supported.")

                def log_subprocess_output(pipe, stop_event):
                    # Read lines until the pipe is closed (EOF)
                    for line in iter(pipe.readline, ""):
                        if not stop_event.is_set():
                            print(line, end="")
                    print("server log tracking thread stopped successfully.")

                # Start threads to read and print stdout and stderr
                stdout_thread = threading.Thread(
                    target=log_subprocess_output, args=(process.stdout, self._stop_event)
                )
                stderr_thread = threading.Thread(
                    target=log_subprocess_output, args=(process.stderr, self._stop_event)
                )
                stdout_thread.setDaemon(True)
                stderr_thread.setDaemon(True)
                stdout_thread.start()
                stderr_thread.start()

            self._server_process = process
            self._stdout_thread = stdout_thread
            self._stderr_thread = stderr_thread

            # Wait for the server to be ready
            server_ready = False
            while not server_ready:
                # Check if the process has terminated unexpectedly
                if not skip_server_setup and process.poll() is not None:
                    # Output the captured logs
                    stdout, stderr = process.communicate()
                    print(stdout)
                    print(stderr)
                    raise Exception(
                        f"Subprocess terminated unexpectedly with code {process.returncode}"
                    )
                try:
                    # Make a simple request to check if the server is up
                    response = requests.get(f"{self.base_url}/models")
                    if response.status_code == 200:
                        server_ready = True
                        print("server is ready!")
                except requests.exceptions.ConnectionError:
                    # If the connection is not ready, wait and try again
                    time.sleep(1)

            # Signal threads to stop reading output
            self._stop_event.set()

        except Exception as e:
            # Clean-up everything we already started, then re-raise
            if self._server_process and self._server_process.poll() is None:
                self._server_process.terminate()
            if self._stop_event:
                self._stop_event.set()
            if self._stdout_thread:
                self._stdout_thread.join(timeout=2)
            if self._stderr_thread:
                self._stderr_thread.join(timeout=2)
            raise e

    def shutdown_local_server(self):
        """Terminate the locally launched OSS model server if it is still running."""
        # Ensure the server process is terminated properly
        process = getattr(self, "_server_process", None)
        if process and process.poll() is None:
            process.terminate()
            try:
                # Wait for the process to terminate fully
                process.wait(timeout=15)
                print("Process terminated successfully.")
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()  # Wait again to ensure it's fully terminated
                print("Process killed.")

        # Tell the log-reader threads to stop and wait for them
        if getattr(self, "_stop_event", None):
            self._stop_event.set()
        if getattr(self, "_stdout_thread", None):
            self._stdout_thread.join(timeout=2)
        if getattr(self, "_stderr_thread", None):
            self._stderr_thread.join(timeout=2)

    #### Prompting methods ####

    @override
    def _pre_query_processing_prompting(self, test_entry: dict) -> dict:
        functions: list = test_entry["function"]
        test_entry_id: str = test_entry["id"]

        test_entry["question"][0] = system_prompt_pre_processing_chat_model(
            test_entry["question"][0], functions, test_entry_id
        )

        return {"message": []}
