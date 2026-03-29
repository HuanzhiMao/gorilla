"""
BaseServiceAPI — shared base class for all 23 dummy service APIs.

Centralises state management so that every server inherits:
  - _load_scenario / _reset_to_initial  (init & reset from JSON ground truth)
  - _snapshot_state / _log_state_snapshot / _get_state_log  (state-change logging)
  - _new_id  (deterministic ID generation)
  - _load_failure_config / _check_failure  (failure injection)
  - __eq__   (attribute-level equality used by the eval pipeline)

Subclasses must set three class-level constants:
  _STATE_KEYS          — tuple of attribute names loaded from the scenario dict
  _ID_COUNTER_DEFAULTS — dict mapping prefix → starting counter value
  _DEFAULT_SEED        — int seed for the per-instance RNG
"""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Any, Dict, List


class ServiceFailureError(Exception):
    """Raised by the failure-injection layer when a call should fail.

    Carries a structured error dict identical to the per-server error classes
    so that the eval pipeline formats it consistently.
    """

    def __init__(
        self,
        error_code: str,
        message: str,
        context: Dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.error: Dict[str, Any] = {
            "error_code": error_code,
            "message": message,
        }
        if context:
            self.error["context"] = context

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.error)


class BaseServiceAPI:
    """Base class providing state management for all service API implementations."""

    # -- Subclass overrides --------------------------------------------------
    _STATE_KEYS: tuple = ()
    _ID_COUNTER_DEFAULTS: Dict[str, int] = {}
    _DEFAULT_SEED: int = 0

    # ------------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------------

    def __init__(self) -> None:
        self.user_id: str = ""
        self._rng: random.Random = random.Random(self._DEFAULT_SEED)
        self._id_counters: Dict[str, int] = dict(self._ID_COUNTER_DEFAULTS)
        self._initial_state: Dict[str, Any] = {}
        self._state_log: List[Dict[str, Any]] = []
        self._failure_config: List[Dict[str, Any]] = []
        self._failure_call_counts: Dict[str, int] = {}

    def _load_scenario(
        self,
        scenario: Dict[str, Any],
        long_context: bool = False,
    ) -> None:
        """Load scenario state from a dict (typically deserialized from the
        ground-truth JSON).  Called by the evaluation pipeline before each test
        and by ``_reset_to_initial``."""
        self._rng = random.Random(scenario.get("random_seed", self._DEFAULT_SEED))
        self.user_id = scenario.get("current_user_id", "")
        self._id_counters = dict(self._ID_COUNTER_DEFAULTS)
        self._initial_state = deepcopy(scenario)
        self._state_log = []

        for key in self._STATE_KEYS:
            setattr(self, key, scenario.get(key, {}))

    def _reset_to_initial(self) -> None:
        """Restore the instance to its initial state (the last scenario that
        was loaded via ``_load_scenario``)."""
        self._load_scenario(deepcopy(self._initial_state))

    # ------------------------------------------------------------------------
    # State snapshot / logging
    # ------------------------------------------------------------------------

    def _snapshot_state(self) -> Dict[str, Any]:
        """Return a deep copy of all *public* (non-underscore) attributes.

        This follows the same convention used by ``__eq__`` and the eval
        pipeline's ``_compare_instances`` helper.
        """
        return {k: deepcopy(v) for k, v in vars(self).items() if not k.startswith("_")}

    def _log_state_snapshot(self, func_call: str) -> None:
        """Append a full state snapshot (tagged with *func_call*) to the
        in-memory log."""
        self._state_log.append(
            {
                "func_call": func_call,
                "state": self._snapshot_state(),
            }
        )

    def _get_state_log(self) -> List[Dict[str, Any]]:
        """Return a deep copy of the accumulated state log."""
        return deepcopy(self._state_log)

    # ------------------------------------------------------------------------
    # ID generation
    # ------------------------------------------------------------------------

    def _new_id(self, prefix: str) -> str:
        """Generate the next sequential ID for *prefix* (e.g. ``order_1``)."""
        self._id_counters[prefix] = self._id_counters.get(prefix, 0) + 1
        return f"{prefix}_{self._id_counters[prefix]}"

    # ------------------------------------------------------------------------
    # Failure injection
    # ------------------------------------------------------------------------

    def _load_failure_config(self, failures: List[Dict[str, Any]]) -> None:
        """Load failure rules that apply to this server instance.

        Each entry in *failures* is a dict with keys:
          - function:      str | None  (None = whole server)
          - type:          "permanent" | "temporary"
          - fail_times:    int  (only used when type == "temporary")
          - error_code:    str
          - error_message: str
          - error_context: dict  (optional extra context included in the error)
          - silent:        bool  (if True, no error is raised; the call
                           executes but state changes are reverted)
        """
        self._failure_config = list(failures)
        self._failure_call_counts = {}

    def _check_failure(self, function_name: str) -> None:
        """Raise ``ServiceFailureError`` if *function_name* should fail
        according to the loaded failure config.

        For **permanent** failures the call always raises.
        For **temporary** failures the call raises for the first
        ``fail_times`` invocations, then passes through.
        Silent failures (``silent=True``) are handled separately via
        ``_is_silent_failure`` and do NOT raise here.
        """
        for rule in self._failure_config:
            target = rule.get("function")
            if target is not None and target != function_name:
                continue

            # Silent failures are not handled by _check_failure
            if rule.get("silent", False):
                continue

            fail_type = rule.get("type", "permanent")
            error_context = rule.get("error_context")

            if fail_type == "permanent":
                raise ServiceFailureError(
                    rule.get("error_code", "SERVICE_UNAVAILABLE"),
                    rule.get("error_message", "Service unavailable."),
                    context=error_context,
                )

            if fail_type == "temporary":
                key = target or "__all__"
                count = self._failure_call_counts.get(key, 0)
                fail_times = rule.get("fail_times", 3)
                if count < fail_times:
                    self._failure_call_counts[key] = count + 1
                    raise ServiceFailureError(
                        rule.get("error_code", "TEMPORARY_FAILURE"),
                        rule.get("error_message", "Service temporarily unavailable."),
                        context=error_context,
                    )
                # count >= fail_times → pass through, service recovered

    def _is_silent_failure(self, function_name: str) -> bool:
        """Return True if *function_name* should execute but have its state
        changes silently reverted (the return value is kept).

        Used by the executor: snapshot state before call, execute normally,
        then revert state if this returns True.
        """
        for rule in self._failure_config:
            if not rule.get("silent", False):
                continue
            target = rule.get("function")
            if target is not None and target != function_name:
                continue

            fail_type = rule.get("type", "permanent")
            if fail_type == "permanent":
                return True

            if fail_type == "temporary":
                key = f"silent_{target or '__all__'}"
                count = self._failure_call_counts.get(key, 0)
                fail_times = rule.get("fail_times", 3)
                if count < fail_times:
                    self._failure_call_counts[key] = count + 1
                    return True
        return False

    # ------------------------------------------------------------------------
    # Equality (used by the eval pipeline's state_checker)
    # ------------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        for attr_name in vars(self):
            if attr_name.startswith("_"):
                continue
            if getattr(self, attr_name) != getattr(other, attr_name):
                return False
        return True
