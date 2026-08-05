import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

import requests
from bfcl_eval.constants.enums import ModelStyle
from bfcl_eval.constants.eval_config import LOCAL_SERVER_PORT
from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)
from bfcl_eval.model_handler.utils import render_messages_for_log
from openai import OpenAI
from overrides import EnforceOverrides, final, override


class OSSHandler(OpenAICompletionsHandler, EnforceOverrides):
    # vLLM's OpenAI-compatible server parses `image_url` and `input_audio` parts for
    # every role and needs no extra flags for `data:` URLs (audio additionally needs
    # the server installed with the `audio` extra). Which of the ~46 served models
    # actually has an image or audio tower is decided per model by
    # `supports_image_input` / `supports_audio_input` in model_config.py.
    can_handle_audio_input = True
    can_handle_image_input = True
    # Deliberately via the inherited user-message workaround rather than an image
    # part inside a `tool` message: vLLM forwards the part to the chat template, and
    # whether that renders, is ignored, or hard-errors is per-template (Gemma 4
    # renders it, Inkling rejects it). The workaround works on every vision model.
    can_handle_image_tool_response = True

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        **kwargs,
    ) -> None:
        super().__init__(model_name, temperature, registry_name, **kwargs)
        self.model_name_huggingface = model_name
        self.model_style = ModelStyle.OSSMODEL

        self.reasoning_parser = None
        self.tool_call_parser = None
        # Extra CLI args appended to `vllm serve ...`
        self.vllm_extra_serve_args: list[str] = []
        # Per-request fields merged into the OpenAI client's extra_body at inference time
        self.inference_request_extra_body: dict = {}

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
        if getattr(self, "inference_request_extra_body", None):
            extra_body.update(self.inference_request_extra_body)
        return extra_body

    def _resolve_tool_call_parser(self) -> str | None:
        return os.getenv("VLLM_TOOL_CALL_PARSER", self.tool_call_parser)

    def _resolve_reasoning_parser(self) -> str | None:
        return os.getenv("VLLM_REASONING_PARSER", self.reasoning_parser)

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
                    reasoning_parser = self._resolve_reasoning_parser()
                    tool_call_parser = self._resolve_tool_call_parser()
                    if not tool_call_parser:
                        raise ValueError(
                            "Function calling models require a supported vLLM tool call parser. "
                            "Set VLLM_TOOL_CALL_PARSER or update the model handler."
                        )
                    cmd = [
                        "vllm",
                        "serve",
                        str(self.model_path_or_id),
                        "--port",
                        str(self.local_server_port),
                        "--tensor-parallel-size",
                        str(num_gpus),
                        "--gpu-memory-utilization",
                        str(gpu_memory_utilization),
                        "--trust-remote-code",
                    ]
                    if tool_call_parser:
                        cmd.extend(
                            [
                                "--enable-auto-tool-choice",
                                "--tool-call-parser",
                                tool_call_parser,
                            ]
                        )
                    if reasoning_parser:
                        cmd.extend(["--reasoning-parser", reasoning_parser])
                    if self.vllm_extra_serve_args:
                        cmd.extend(self.vllm_extra_serve_args)
                    if enable_lora:
                        cmd.append("--enable-lora")
                    if max_lora_rank is not None:
                        cmd.extend(["--max-lora-rank", str(max_lora_rank)])
                    if lora_modules:
                        for lora_module in lora_modules:
                            cmd.extend(["--lora-modules", lora_module])

                    print(f"🚀 Starting vLLM server with command: \"{' '.join(cmd)}\"")

                    # @HuanzhiMao FIXME: test this
                    # Build a clean env so the parent's restricted threading
                    # settings (OMP_NUM_THREADS=1, etc.) don't throttle vLLM.
                    env = os.environ.copy()
                    for var in (
                        "OMP_NUM_THREADS",
                        "MKL_NUM_THREADS",
                        "TOKENIZERS_PARALLELISM",
                    ):
                        env.pop(var, None)

                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,  # Capture stdout
                        stderr=subprocess.PIPE,  # Capture stderr
                        text=True,  # To get the output as text instead of bytes
                        env=env,
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
            print("🔄 Waiting for server to be ready... (this may take a few minutes)")
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
                        print("🙌 Server is ready!\n")
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

    #### FC methods ####

    @override
    def _query_FC(self, inference_data: dict):
        message: list[dict] = inference_data["message"]
        tools = inference_data["tools"]
        inference_data["inference_input_log"] = {"message": render_messages_for_log(message), "tools": tools}

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
