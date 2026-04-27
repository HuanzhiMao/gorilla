"""Runtime patches for UberAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.uber import UberAPI, UberError
from datetime import datetime, timedelta
import uuid

# ─── Source: socrates ───


@UberAPI._register_patch("request_ride", "phantom_permanent")
def request_ride_phantom_permanent(self, *args, **kwargs):
    """Permanent phantom. Returns fake accepted ride without ever creating it.
    The ride never exists in the system, so get_ride_status will correctly fail."""
    return {
        "ride_id": f"ride_{uuid.uuid4().hex[:8]}",
        "status": "accepted",
        "fare_total": 25.0,
        "surge_multiplier": 1.0,
        "eta_pickup_min": 5,
    }


@UberAPI._register_patch("request_ride", "unavailable_permanent")
def request_ride_unavailable_permanent(self, *args, **kwargs):
    """Permanent. Always raises SERVICE_UNAVAILABLE."""
    raise UberError(
        "SERVICE_UNAVAILABLE",
        "Uber service is currently unavailable in your area.",
        "Try using an alternative ride service like Lyft.",
    )


# ─── Source: yash ───


# ft_013 -- ride type downgrade (e.g. XL -> UberX)
@UberAPI._register_patch("request_ride", "downgrade")
def request_ride_downgrade(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    ride_id = result["ride_id"]
    result["ride_type_id"] = "UberX"
    result["capacity"] = 4
    if "driver" in result:
        result["driver"]["vehicle"] = {"make": "Toyota", "model": "Camry", "year": 2022, "color": "Silver"}
    if ride_id in self.rides:
        self.rides[ride_id]["ride_type"] = "UberX"
        self.rides[ride_id]["capacity"] = 4
    return result


# ft_015 -- replacement ride unavailable
@UberAPI._register_patch("request_ride", "replacementunavailable")
def request_ride_replacementunavailable(self, *args, **kwargs):
    raise UberError(
        "SERVICE_UNAVAILABLE",
        "Uber replacement rides are unavailable in this scenario.",
    )


# ft_016 -- pool is full
@UberAPI._register_patch("request_ride", "poolfull")
def request_ride_poolfull(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    ride_id = result["ride_id"]
    result["ride_type_id"] = "Pool"
    result["pool_passengers"] = 4
    result["max_capacity"] = 4
    result["remaining_seats_before_booking"] = 0
    if ride_id in self.rides:
        self.rides[ride_id]["ride_type_id"] = "Pool"
        self.rides[ride_id]["pool_passengers"] = 4
        self.rides[ride_id]["max_capacity"] = 4
        self.rides[ride_id]["remaining_seats_before_booking"] = 0
    return result


# ft_020 -- service unavailable
@UberAPI._register_patch("request_ride", "unavailable")
def request_ride_unavailable(self, *args, **kwargs):
    raise UberError(
        "SERVICE_UNAVAILABLE",
        "Uber service is unavailable for this trip.",
    )


# ft_015 -- impossible ETA (arrival before creation)
@UberAPI._register_patch("list_rides", "impossibleeta")
def list_rides_impossibleeta(self, *args, **kwargs):
    for ride in self.rides.values():
        if "created_at" in ride:
            created_at = datetime.fromisoformat(ride["created_at"])
            ride["estimated_arrival"] = (created_at - timedelta(minutes=5)).isoformat()
    return self._original_function(*args, **kwargs)


# ft_014 -- surge glitch on all-type estimate
@UberAPI._register_patch("get_price_estimates", "surgeglitch")
def get_price_estimates_surgeglitch(self, *args, **kwargs):
    results = self._original_function(*args, **kwargs)
    for entry in results:
        entry["surge_fee_charged"] = True
        if entry.get("ride_type_id", "").lower() in ("uber_x", "uberx"):
            entry["surge_charge_should_be_waived_by_uber_pass"] = True
            entry["membership_plan"] = "Uber Pass"
            entry["surge_fee_amount"] = 12.0
            entry["estimated_fare"] = round(entry["estimated_fare"] + 12.0, 2)
    return results


# ft_014 -- blocked (forces LLM to use get_price_estimates)
@UberAPI._register_patch("estimate_ride", "blocked")
def estimate_ride_blocked(self, *args, **kwargs):
    raise UberError(
        "FEATURE_DISABLED",
        "Individual ride estimates are not available. Use get_price_estimates instead.",
    )


# ---------- reserve_ride ----------


# ft_extra_36 -- availability_denial/temporary. First call rejects with
# RESERVE_WINDOW_CLOSED for the requested scheduled_time -- the Uber
# Reserve booking horizon briefly closed for that pickup zone (e.g.
# during a region-wide schedule refresh). Second call falls through.
@UberAPI._register_patch("reserve_ride", "reserve_window_closed_temporary")
def reserve_ride_reserve_window_closed_temporary(self, *args, **kwargs):
    """Temporary. First call raises RESERVE_WINDOW_CLOSED with a clear
    retryable hint; second call falls through."""
    if self._patch_call_count <= 1:
        raise UberError(
            "RESERVE_WINDOW_CLOSED",
            "Uber Reserve booking horizon is briefly closed for this pickup "
            "zone. The window typically reopens within seconds.",
            "Retry the same request once -- the closure is short.",
        )
    return self._original_function(*args, **kwargs)
