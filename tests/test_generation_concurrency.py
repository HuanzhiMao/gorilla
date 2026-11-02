"""Generation concurrency defaults are conservative for shared GeoGuessr servers."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from bfcl_eval import _llm_response_generation as generation
from bfcl_eval.schemas.category import TestCategory


@pytest.mark.parametrize(
    "oss,categories,requested,expected",
    [
        (True, ["vision:geoguessr_type1"], None, 8),
        (True, ["vision:geoguessr_type1_competition"], None, 8),
        (True, ["vision:geoguessr_type2"], None, 8),
        (True, ["vision:geoguessr_type3"], None, 8),
        (True, ["text:simple_python"], None, 100),
        (True, ["vision:vision_web_search_base"], None, 100),
        (True, ["text:simple_python", "vision:geoguessr_type1"], None, 8),
        (False, ["vision:geoguessr_type1"], None, 1),
        (False, ["text:simple_python"], None, 1),
        (True, ["vision:geoguessr_type1"], 32, 32),
        (False, ["vision:geoguessr_type1"], 32, 32),
        (True, ["vision:geoguessr_type1"], 2, 2),
    ],
)
def test_generation_executor_concurrency(monkeypatch, oss, categories, requested, expected):
    class OSSProbe:
        spin_up_local_server = Mock()
        shutdown_local_server = Mock()

    handler = OSSProbe() if oss else Mock()
    monkeypatch.setattr(generation, "OSSHandler", OSSProbe)
    monkeypatch.setattr(generation, "build_handler", lambda *args: handler)
    executor = Mock(side_effect=RuntimeError("executor reached"))
    monkeypatch.setattr(generation, "ThreadPoolExecutor", executor)
    entries = [
        SimpleNamespace(
            id=f"{category}_0", category=TestCategory.from_value(category), depends_on=[]
        )
        for category in categories
    ]
    args = generation.Args(
        temperature=0.01,
        num_threads=requested,
        num_gpus=1,
        gpu_memory_utilization=0.9,
        backend="vllm",
        skip_server_setup=True,
        local_model_path=None,
        lora_modules=None,
        enable_lora=False,
        max_lora_rank=None,
    )

    # Stop at executor creation: run the real selection path without provider calls.
    with pytest.raises(RuntimeError, match="executor reached"):
        generation.generate_results(args, "fixture", entries)

    executor.assert_called_once_with(max_workers=expected)
    if oss:
        handler.shutdown_local_server.assert_called_once_with()
