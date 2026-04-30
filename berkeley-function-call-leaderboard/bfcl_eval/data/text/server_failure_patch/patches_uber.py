"""Runtime patches for UberAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.uber import (
    UberAPI,
    UberError,
    _haversine_miles,
)
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
    raise UberError("SERVICE_UNAVAILABLE", "")


# ─── Source: yash ───


# ft_013 -- ride type downgrade (e.g. XL -> UberX)
# Guard: only fires when the model actually requested uber_xl. If the model
# requests a different ride_type, behave normally (rubric pins ride_type_id='uber_xl'
# so a wrong selection deterministically fails the structural check).
@UberAPI._register_patch("request_ride", "downgrade")
def request_ride_downgrade(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    requested_type = kwargs.get("ride_type_id")
    if requested_type is None and len(args) >= 5:
        requested_type = args[4]
    if requested_type != "uber_xl":
        return result
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
    raise UberError("SERVICE_UNAVAILABLE", "")


# ft_016 -- pool is full
# Paired patches:
#   1) get_price_estimates: force uber_pool to appear strictly cheapest so a
#      cost-minimizing agent (user asked for "cheapest") deterministically picks
#      Pool regardless of RNG / seed-driven surge differences.
#   2) request_ride: only inject the full-pool payload when ride_type_id == "uber_pool"
#      (guard prevents pollution of unrelated ride_type requests).
@UberAPI._register_patch("get_price_estimates", "poolfull")
def get_price_estimates_poolfull(
    self, pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
):
    # Inline the original get_price_estimates -> estimate_ride flow so this patch
    # does not delegate through self.estimate_ride (ft_016 blocks estimate_ride
    # to force use of get_price_estimates). The per-ride-type RNG calls are
    # preserved exactly so the fare computation is identical to the original.
    results = []
    for rt_id in self.ride_types:
        rt = self.ride_types[rt_id]
        if not rt.get("available", True):
            continue
        
        # Inline estimate_ride logic for this ride_type
        from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.uber import _haversine_miles
        dist = _haversine_miles(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        duration = max(5, dist * 3)
        surge = self._get_surge_multiplier()
        price = self._compute_fare(dist, duration, rt, surge)
        eta = self._rng.randint(3, 15)
        
        entry = {
            "ride_type_id": rt_id,
            "estimated_fare": price,
            "distance_miles": round(dist, 1),
            "duration_minutes": round(duration),
            "surge_multiplier": surge,
            "eta_pickup_min": eta,
        }
        results.append(entry)
    
    # poolfull mutation: force Pool to be cheapest
    pool = next((r for r in results if r.get("ride_type_id") == "uber_pool"), None)
    others = [r for r in results if r.get("ride_type_id") != "uber_pool"]
    if pool and others:
        cheapest_other = min(r.get("estimated_fare", float("inf")) for r in others)
        pool["estimated_fare"] = round(cheapest_other * 0.7, 2)
        pool["surge_multiplier"] = 1.0
    
    return results


@UberAPI._register_patch("request_ride", "poolfull")
def request_ride_poolfull(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    requested_type = kwargs.get("ride_type_id")
    if requested_type is None and len(args) >= 5:
        requested_type = args[4]
    if requested_type != "uber_pool":
        return result
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
    raise UberError("SERVICE_UNAVAILABLE", "")


# ft_015 -- impossible ETA (arrival before creation)
@UberAPI._register_patch("list_rides", "impossibleeta")
def list_rides_impossibleeta(self, *args, **kwargs):
    for ride in self.rides.values():
        if "created_at" in ride:
            created_at_raw = ride["created_at"]
            if isinstance(created_at_raw, str) and created_at_raw.endswith("Z"):
                created_at_raw = created_at_raw[:-1] + "+00:00"
            created_at = datetime.fromisoformat(created_at_raw)
            ride["estimated_arrival"] = (created_at - timedelta(minutes=5)).isoformat()
    return self._original_function(*args, **kwargs)


# ft_014 -- surge glitch on all-type estimate
@UberAPI._register_patch("get_price_estimates", "surgeglitch")
def get_price_estimates_surgeglitch(
    self, pickup_lat, pickup_lng, dropoff_lat, dropoff_lng
):
    # Inline the original get_price_estimates -> estimate_ride flow so this patch
    # does not delegate through self.estimate_ride (ft_014 also blocks
    # estimate_ride to funnel the agent onto get_price_estimates). The per-iter
    # RNG calls (_get_surge_multiplier, _rng.randint) are preserved exactly so
    # the resulting numbers match what the unpatched delegating call would
    # produce, then the surge-glitch mutation runs on top.
    results = []
    for rt_id in self.ride_types:
        rt = self.ride_types[rt_id]
        if not rt.get("available", True):
            continue
        # Mirror estimate_ride() body exactly so RNG draws happen in the same
        # order and count as the original call would have produced.
        rt_obj = self._require_ride_type(rt_id)
        dist = _haversine_miles(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        duration = max(5, dist * 3)
        surge = self._get_surge_multiplier()
        price = self._compute_fare(dist, duration, rt_obj, surge)
        eta = self._rng.randint(3, 15)
        entry = {
            "ride_type_id": rt_id,
            "estimated_fare": price,
            "distance_miles": round(dist, 1),
            "duration_minutes": round(duration),
            "surge_multiplier": surge,
            "eta_pickup_min": eta,
        }
        # surgeglitch mutation on top of the per-entry estimate.
        entry["surge_fee_charged"] = True
        if entry.get("ride_type_id", "").lower() in ("uber_x", "uberx"):
            entry["surge_charge_should_be_waived_by_uber_pass"] = True
            entry["membership_plan"] = "Uber Pass"
            # surge_fee_amount is intentionally opaque ("hidden") so the model
            # cannot reconstruct a "real" total by adding it back to the
            # estimated_fare. Combined with the displayed cheap fare below,
            # this leaves only two paths: trust the cheap displayed total
            # (-> picks Uber -> fails must_not_be_called) or distrust the
            # contradictory metadata (-> picks Lyft -> passes).
            entry["surge_fee_amount"] = "hidden"
            # Deterministically force uber_x to be cheaper than ANY Lyft option
            # for this scenario's trip (1.5 mi, prime_time=0% by location hash).
            # Lyft Standard wait_and_save_fare floor for this trip is ~$4.28, so
            # we use $1.99 to stay safely below even the W&S option. The
            # absurdly cheap fare for a 1.5-mile trip also reinforces the
            # contradiction signal alongside the hidden-surge metadata.
            entry["estimated_fare"] = 1.99
        results.append(entry)
    return results


# ft_014 -- blocked (forces LLM to use get_price_estimates)
@UberAPI._register_patch("estimate_ride", "blocked")
def estimate_ride_blocked(self, *args, **kwargs):
    raise UberError("FEATURE_DISABLED", "")


# ---------- request_ride (Uber Reserve / scheduled_time path) ----------


# ft_extra_36 -- availability_denial/temporary. First call rejects with
# RESERVE_WINDOW_CLOSED when scheduled_time is set -- the Uber Reserve
# booking horizon briefly closed for that pickup zone (e.g. during a
# region-wide schedule refresh). Second call falls through. Immediate
# rides (scheduled_time is None) are unaffected by this patch and fall
# through to the original implementation.
@UberAPI._register_patch("request_ride", "reserve_window_closed_temporary")
def request_ride_reserve_window_closed_temporary(self, *args, **kwargs):
    """Temporary. First scheduled-ride call raises RESERVE_WINDOW_CLOSED
    with a clear retryable hint; second scheduled call falls through.
    Immediate-ride calls (scheduled_time is None) always fall through and
    do NOT consume the scheduled-call counter — that way an immediate
    request_ride preceding the scheduled retry doesn't pre-burn the
    failing slot."""
    scheduled_time = kwargs.get("scheduled_time")
    if scheduled_time is None and len(args) >= 6:
        scheduled_time = args[5]
    if not scheduled_time:
        return self._original_function(*args, **kwargs)
    attempts = getattr(self, "_reserve_window_closed_attempts", 0)
    self._reserve_window_closed_attempts = attempts + 1
    if attempts == 0:
        raise UberError(
            "RESERVE_WINDOW_CLOSED",
            "Uber Reserve booking horizon is briefly closed for this pickup "
            "zone. The window typically reopens within seconds.",
            "Retry the same request once -- the closure is short.",
        )
    return self._original_function(*args, **kwargs)


# ─── Source: yash (alternate-path blockers) ───
# These "blocked" patches close off alternate paths the LLM might take to the
# same end-state, so the must_be_called_functions deterministic check is not
# defeated by a valid-but-different recovery sequence.

@UberAPI._register_patch("estimate_ride", "blocked_ft016")
def estimate_ride_blocked_ft016(self, *args, **kwargs):
    raise UberError("FEATURE_DISABLED", "")

@UberAPI._register_patch("get_ride", "blocked")
def get_ride_blocked(self, *args, **kwargs):
    raise UberError("FEATURE_DISABLED", "")

@UberAPI._register_patch("list_rides", "blocked")
def list_rides_blocked(self, *args, **kwargs):
    raise UberError("FEATURE_DISABLED", "")
