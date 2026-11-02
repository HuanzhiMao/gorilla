"""GeoGuessr admission waits locally and shares its budget between processes."""

import multiprocessing
import os
import queue
import subprocess
import sys
import threading
import traceback
from pathlib import Path

import pytest
from bfcl_eval import _geoguessr_concurrency as concurrency
from filelock import FileLock, Timeout

SERVER = "http://localhost:18000"


@pytest.fixture
def lock_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(concurrency, "_LOCK_DIR", tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "first,second",
    [
        ("http://localhost", "http://127.0.0.1:80/path?q=1"),
        ("http://LOCALHOST.:18000", "http://[::1]:18000/other"),
        ("https://Example.COM", "https://example.com:443/path"),
        ("http://user:password@example.com/a", "http://example.com:80/b"),
    ],
)
def test_origin_aliases_share_capacity(first, second):
    assert concurrency._origin_key(first) == concurrency._origin_key(second)


@pytest.mark.parametrize("other", ["http://localhost:18001", "https://localhost:18000"])
def test_distinct_origins_have_independent_budgets(other):
    assert concurrency._origin_key(SERVER) != concurrency._origin_key(other)


def test_busy_slots_wait_and_wake_without_connecting(lock_dir, monkeypatch):
    monkeypatch.setattr(concurrency, "MAX_CONCURRENT_EPISODES", 1)
    waiting, admitted = threading.Event(), threading.Event()
    original_sleep = concurrency.time.sleep

    def observed_sleep(seconds):
        waiting.set()
        original_sleep(seconds)

    monkeypatch.setattr(concurrency.time, "sleep", observed_sleep)

    def waiter():
        with concurrency.geoguessr_episode_slot("http://[::1]:18000/path"):
            admitted.set()

    thread = threading.Thread(target=waiter, daemon=True)
    with concurrency.geoguessr_episode_slot(SERVER):
        thread.start()
        assert waiting.wait(3), "worker did not wait for admission"
        assert not admitted.is_set()
    assert admitted.wait(3), "worker did not acquire the released slot"
    thread.join(timeout=3)
    assert not thread.is_alive()
    # Slot files must survive release, or concurrent users may lock different inodes.
    assert len(list(lock_dir.glob("*.lock"))) == 1


def test_body_exception_releases_slot_without_retrying_it(lock_dir, monkeypatch):
    monkeypatch.setattr(concurrency, "MAX_CONCURRENT_EPISODES", 1)
    attempts = []
    with pytest.raises(Timeout), concurrency.geoguessr_episode_slot(SERVER):
        attempts.append("episode")
        raise Timeout("unrelated-inference-lock")
    assert attempts == ["episode"]
    with FileLock(next(lock_dir.glob("*.lock"))).acquire(timeout=1):
        pass


def test_body_runtime_error_is_not_wrapped_as_admission_failure(lock_dir):
    error = RuntimeError("inference failed")
    with pytest.raises(RuntimeError) as caught, concurrency.geoguessr_episode_slot(SERVER):
        raise error
    assert caught.value is error


def test_unusable_lock_directory_is_an_admission_error(lock_dir, monkeypatch):
    file = lock_dir / "file"
    file.write_text("not a directory")
    monkeypatch.setattr(concurrency, "_LOCK_DIR", file)
    with (
        pytest.raises(concurrency.GeoGuessrAdmissionError, match="prepare"),
        concurrency.geoguessr_episode_slot(SERVER),
    ):
        pytest.fail("inference must not start without the shared gate")


def test_lock_acquisition_os_error_is_an_admission_error(lock_dir, monkeypatch):
    def fail_acquire(*args, **kwargs):
        raise PermissionError("lock permission denied")

    monkeypatch.setattr(concurrency.FileLock, "acquire", fail_acquire)
    with (
        pytest.raises(concurrency.GeoGuessrAdmissionError, match="acquire"),
        concurrency.geoguessr_episode_slot(SERVER),
    ):
        pytest.fail("inference must not start without the shared gate")


def test_lock_release_os_error_is_an_admission_error(lock_dir, monkeypatch):
    release = concurrency.FileLock.release

    def fail_release(self, force=False):
        release(self, force=force)
        if not force:
            raise PermissionError("lock release failed")

    monkeypatch.setattr(concurrency.FileLock, "release", fail_release)
    with (
        pytest.raises(concurrency.GeoGuessrAdmissionError, match="release"),
        concurrency.geoguessr_episode_slot(SERVER),
    ):
        pass


def test_other_server_can_enter_while_first_is_full(lock_dir, monkeypatch):
    monkeypatch.setattr(concurrency, "MAX_CONCURRENT_EPISODES", 1)
    entered = threading.Event()

    def other_server():
        with concurrency.geoguessr_episode_slot("http://localhost:18001"):
            entered.set()

    with concurrency.geoguessr_episode_slot(SERVER):
        thread = threading.Thread(target=other_server, daemon=True)
        thread.start()
        assert entered.wait(3)
        thread.join(timeout=3)
        assert not thread.is_alive()


def _hold_process_slots(lock_dir, workers, count, peak, completed, full, release, errors):
    """Use real process locks and several client threads in each spawned process."""
    from bfcl_eval import _geoguessr_concurrency as limiter

    limiter._LOCK_DIR = Path(lock_dir)

    def hold():
        try:
            with limiter.geoguessr_episode_slot(SERVER):
                with count.get_lock():
                    count.value += 1
                    peak.value = max(peak.value, count.value)
                    if count.value == limiter.MAX_CONCURRENT_EPISODES:
                        full.set()
                try:
                    if not release.wait(10):
                        raise RuntimeError("test did not release admitted episodes")
                finally:
                    with count.get_lock():
                        count.value -= 1
                        completed.value += 1
        except (RuntimeError, OSError, Timeout):
            errors.put(traceback.format_exc())

    threads = [threading.Thread(target=hold, daemon=True) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)
    if any(thread.is_alive() for thread in threads):
        errors.put("a worker remained blocked")


def test_eight_slot_budget_is_shared_by_threads_and_processes(lock_dir):
    assert concurrency.MAX_CONCURRENT_EPISODES == 8
    context = multiprocessing.get_context("spawn")
    count, peak, completed = (context.Value("i", 0) for _ in range(3))
    full, release = context.Event(), context.Event()
    errors = context.Queue()
    processes = [
        context.Process(target=_hold_process_slots, args=(
            str(lock_dir), 6, count, peak, completed, full, release, errors,
        ))
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    try:
        assert full.wait(8), "processes did not fill the eight available slots"
        assert count.value == 8
        assert peak.value == 8
    finally:
        release.set()
        for process in processes:
            process.join(timeout=10)
            if process.is_alive():
                process.kill()
                process.join(timeout=3)
    assert all(process.exitcode == 0 for process in processes)
    failures = []
    while True:
        try:
            failures.append(errors.get_nowait())
        except queue.Empty:
            break
    assert not failures, failures
    assert completed.value == 12
    assert count.value == 0
    assert peak.value == 8


def _hold_until_killed(lock_dir, entered):
    from bfcl_eval import _geoguessr_concurrency as limiter

    limiter._LOCK_DIR = Path(lock_dir)
    limiter.MAX_CONCURRENT_EPISODES = 1
    with limiter.geoguessr_episode_slot(SERVER):
        entered.set()
        threading.Event().wait(30)


def test_killed_process_releases_its_slot(lock_dir):
    context = multiprocessing.get_context("spawn")
    entered = context.Event()
    process = context.Process(target=_hold_until_killed, args=(str(lock_dir), entered))
    process.start()
    try:
        assert entered.wait(8)
    finally:
        process.kill()
        process.join(timeout=3)
    assert not process.is_alive()
    with FileLock(next(lock_dir.glob("*.lock"))).acquire(timeout=2):
        pass


@pytest.mark.skipif(os.name != "posix", reason="POSIX uses a fixed common /tmp root")
def test_run_output_and_temp_overrides_do_not_split_the_budget(tmp_path):
    directories = []
    for name in ("first", "second"):
        environment = dict(os.environ, BFCL_PROJECT_ROOT=str(tmp_path / name), TMPDIR=str(tmp_path / name))
        directories.append(subprocess.check_output([
            sys.executable, "-c",
            "from bfcl_eval._geoguessr_concurrency import _LOCK_DIR; print(_LOCK_DIR)",
        ], env=environment, text=True).strip())
    assert directories == ["/tmp/bfcl-geoguessr-slots"] * 2
