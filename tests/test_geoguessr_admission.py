"""Episode admission covers initialization and teardown without changing model results."""

from contextlib import contextmanager
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from bfcl_eval import _geoguessr_concurrency as concurrency
from bfcl_eval import _llm_response_generation as generation
from bfcl_eval._geoguessr_concurrency import GeoGuessrAdmissionError
from bfcl_eval.constants.enums import Modality
from bfcl_eval.model_handler import base_handler
from bfcl_eval.schemas.category import TestCategory


def entry(category="vision:geoguessr_type1"):
    return SimpleNamespace(
        id=f"{category}_0",
        category=TestCategory.from_value(category),
        environment=SimpleNamespace(
            initial_config={}, involved_classes=["StreetViewAPI"], failure_injections=[]
        ),
    )


@pytest.mark.parametrize("model_fails", [False, True])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_slot_covers_initialization_and_cleanup(monkeypatch, model_fails, cleanup_fails):
    trace = []
    server_url = "http://geoguessr.test:18000"
    monkeypatch.setenv("GEOGUESSR_SERVER_URL", server_url)

    @contextmanager
    def admission(url):
        assert url == server_url
        trace.append("admitted")
        try:
            yield
        finally:
            trace.append("released")

    monkeypatch.setattr(base_handler, "geoguessr_episode_slot", admission)
    handler = base_handler.BaseHandler.__new__(base_handler.BaseHandler)
    handler.model_name_underline_replaced = "admission_probe"
    backend = SimpleNamespace()

    def cleanup():
        trace.append("cleanup")
        if cleanup_fails:
            raise RuntimeError("cleanup failed")

    backend._end_session = cleanup

    def initialize(*args, **kwargs):
        trace.append("initialize")
        return [], {"StreetViewAPI": backend}

    monkeypatch.setattr(base_handler, "execute_multi_turn_func_call", initialize)
    monkeypatch.setattr(
        base_handler, "evict_multi_turn_backend_instance", lambda *args: trace.append("evicted")
    )
    expected = ([["answer"]], {"latency": [[0.25]]})
    model_error = RuntimeError("model failed")

    def infer(*args):
        trace.append("model")
        if model_fails:
            raise model_error
        return expected

    handler._inference_multi_turn_FC = infer
    if model_fails:
        with pytest.raises(RuntimeError) as caught:
            handler.inference(entry(), False, True)
        assert caught.value is model_error
    else:
        assert handler.inference(entry(), False, True) is expected

    assert trace == ["admitted", "initialize", "model", "cleanup", "evicted", "released"]


@pytest.mark.parametrize("category", ["text:simple_python", "vision:vision_web_search_base"])
def test_non_geoguessr_inference_does_not_acquire_slot(monkeypatch, category):
    admission = Mock(side_effect=AssertionError("unrelated category acquired admission"))
    monkeypatch.setattr(base_handler, "geoguessr_episode_slot", admission)
    handler = base_handler.BaseHandler.__new__(base_handler.BaseHandler)
    expected = object()
    handler.inference_multi_turn_FC = Mock(return_value=expected)
    test_entry = entry(category)

    assert handler.inference(test_entry, False, True) is expected

    admission.assert_not_called()
    handler.inference_multi_turn_FC.assert_called_once_with(test_entry, False, True)


def test_admission_failure_propagates_before_backend_initialization(monkeypatch):
    failure = GeoGuessrAdmissionError("cannot access admission lock directory")

    @contextmanager
    def admission(url):
        raise failure
        yield

    monkeypatch.setattr(base_handler, "geoguessr_episode_slot", admission)
    handler = base_handler.BaseHandler.__new__(base_handler.BaseHandler)
    handler.inference_multi_turn_FC = Mock()

    with pytest.raises(GeoGuessrAdmissionError) as caught:
        handler.inference(entry(), False, True)

    assert caught.value is failure
    handler.inference_multi_turn_FC.assert_not_called()


def test_generation_does_not_record_admission_failure_as_model_failure(monkeypatch):
    failure = GeoGuessrAdmissionError("cannot acquire admission slot")

    @contextmanager
    def admission(url):
        raise failure
        yield

    monkeypatch.setattr(base_handler, "geoguessr_episode_slot", admission)
    handler = base_handler.BaseHandler.__new__(base_handler.BaseHandler)
    handler.inference_multi_turn_FC = Mock()
    test_entry = entry()
    test_entry.functions = []
    test_entry.modality = Modality.VISION

    with pytest.raises(GeoGuessrAdmissionError) as caught:
        generation.multi_threaded_inference(handler, test_entry, False, True)

    assert caught.value is failure
    handler.inference_multi_turn_FC.assert_not_called()


def test_generation_still_records_ordinary_model_failures():
    handler = Mock()
    handler.inference.side_effect = RuntimeError("provider unavailable")
    test_entry = entry()
    test_entry.functions = []
    test_entry.modality = Modality.VISION

    result = generation.multi_threaded_inference(handler, test_entry, False, True)

    assert result.failed
    assert "provider unavailable" in result.result


def test_full_capacity_waits_before_fc_initialization(monkeypatch, tmp_path):
    monkeypatch.setattr(concurrency, "_LOCK_DIR", tmp_path)
    monkeypatch.setattr(concurrency, "MAX_CONCURRENT_EPISODES", 1)
    server_url = "http://admission.test:18000"
    monkeypatch.setenv("GEOGUESSR_SERVER_URL", server_url)
    handler = base_handler.BaseHandler.__new__(base_handler.BaseHandler)
    expected = object()
    handler.inference_multi_turn_FC = Mock(return_value=expected)
    attempted = Event()
    results, errors = [], []

    class ObservedLock(concurrency.FileLock):
        def acquire(self, *args, **kwargs):
            attempted.set()
            return super().acquire(*args, **kwargs)

    def infer():
        try:
            results.append(handler.inference(entry(), False, True))
        except (AssertionError, OSError, RuntimeError) as error:
            errors.append(error)

    thread = Thread(target=infer, daemon=True)
    try:
        with concurrency.geoguessr_episode_slot(server_url):
            monkeypatch.setattr(concurrency, "FileLock", ObservedLock)
            thread.start()
            assert attempted.wait(5), "waiting episode did not attempt admission"
            handler.inference_multi_turn_FC.assert_not_called()
    finally:
        if thread.ident is not None:
            thread.join(timeout=5)

    assert not thread.is_alive()
    assert errors == []
    assert results == [expected]
    handler.inference_multi_turn_FC.assert_called_once()
