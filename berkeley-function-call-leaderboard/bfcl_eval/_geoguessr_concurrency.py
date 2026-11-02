"""Share GeoGuessr episode capacity across BFCL processes on one machine."""

import hashlib
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from filelock import FileLock, Timeout

MAX_CONCURRENT_EPISODES = 8
# Run-specific output paths and TMPDIR must not create independent budgets.
_LOCK_DIR = Path("/tmp" if os.name == "posix" else tempfile.gettempdir()) / "bfcl-geoguessr-slots"


class GeoGuessrAdmissionError(RuntimeError):
    """The shared capacity gate could not be used; abort rather than score errors."""


def _origin_key(server_url: str) -> str:
    url = urlsplit(server_url)
    scheme = url.scheme.lower()
    host = (url.hostname or "").lower().rstrip(".")
    if scheme not in {"http", "https"} or not host:
        raise ValueError("GEOGUESSR_SERVER_URL must be an absolute HTTP(S) URL")
    if host in {"localhost", "127.0.0.1", "::1"}:
        host = "localhost"
    port = url.port
    if port is None:
        port = 443 if scheme == "https" else 80
    origin = f"{scheme}://{host}:{port}"
    return hashlib.sha256(origin.encode("utf-8")).hexdigest()


@contextmanager
def geoguessr_episode_slot(server_url: str):
    """Wait for capacity before an episode creates its server connection.

    Processes using this machine and server origin share eight slots. Different
    machines need a shared admission mechanism; arbitrary DNS aliases should use
    the same server URL. Kernel locks are released if a process dies. Slot files
    stay in place so every process continues locking the same inodes.
    """
    try:
        key = _origin_key(server_url)
        _LOCK_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        locks = [FileLock(_LOCK_DIR / f"{key}.{slot}.lock") for slot in range(MAX_CONCURRENT_EPISODES)]
    except (OSError, ValueError) as error:
        raise GeoGuessrAdmissionError(f"Unable to prepare GeoGuessr admission slots: {error}") from error
    while True:
        for lock in locks:
            try:
                lock.acquire(timeout=0)
            except Timeout:
                continue
            except OSError as error:
                raise GeoGuessrAdmissionError(f"Unable to acquire a GeoGuessr admission slot: {error}") from error
            try:
                yield
            finally:
                try:
                    lock.release()
                except OSError as error:
                    raise GeoGuessrAdmissionError(f"Unable to release a GeoGuessr admission slot: {error}") from error
            return
        # Saturation waits locally, rather than becoming a failed benchmark entry.
        time.sleep(0.05)
