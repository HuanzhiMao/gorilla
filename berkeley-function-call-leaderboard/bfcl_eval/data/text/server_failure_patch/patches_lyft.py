"""Runtime patches for LyftAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.lyft import LyftAPI, LyftError

# ─── Source: patches_lyft.py ───


# ---------- get_ride_estimates ----------

# ft_012 -- fare breakdown mismatch
@LyftAPI._register_patch("get_ride_estimates", "breakdownmismatch")
def get_ride_estimates_breakdownmismatch(self, *args, **kwargs):
    results = self._original_function(*args, **kwargs)
    if results:
        results[0].pop("estimated_fare", None)
        results[0].pop("wait_and_save_fare", None)
        results[0]["fare"] = 18.0
        results[0]["fare_breakdown"] = {"base_fare": 10.0, "distance_fee": 8.0, "time_fee": 8.0}
        results[0]["discount_applied"] = 0.0
        results[0]["promotions"] = None
    return results


# ft_019 -- negative fare entry (targets XL by ride_type_id)
@LyftAPI._register_patch("get_ride_estimates", "invalidentry")
def get_ride_estimates_invalidentry(self, *args, **kwargs):
    results = self._original_function(*args, **kwargs)
    for entry in results:
        if entry.get("ride_type_id", "").lower() == "xl":
            entry["estimated_fare"] = -5.0
            break
    return results


# ---------- request_ride ----------

# ft_017 -- capacity violation (XL returns capacity=4)
# Guard: only fires when the model actually requested ride_type_id='xl'. If the
# model picks a different ride_type, the call passes through unmodified.
# Rubric pins ride_type_id='xl' so wrong-type selection deterministically fails
# the structural check rather than silently masking the failure with mutated data.
@LyftAPI._register_patch("book_ride", "capacityviolation")
def book_ride_capacityviolation(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    requested_type = kwargs.get("ride_type_id")
    if requested_type is None and len(args) >= 5:
        requested_type = args[4]
    if requested_type != "xl":
        return result
    ride_id = result["ride_id"]
    result["ride_type_id"] = "xl"
    result["capacity"] = 4
    if ride_id in self.rides:
        self.rides[ride_id]["ride_type_id"] = "xl"
        self.rides[ride_id]["capacity"] = 4
    return result


# ft_020 -- fixed fare override (Lyft side of cross-platform scenario)
# Guard: only fires when the model actually booked ride_type_id='standard'. If the
# model picks a different ride_type, the call passes through unmodified -- a wrong
# selection then yields a non-$30 fare, causing the downstream Venmo half-split
# rubric (request_money(amount=15.0)) to fail the structural check instead of
# being silently masked. TODO: tighten the prompt to explicitly request a Lyft
# Standard ride and update the rubric to pin ride_type_id='standard' on book_ride.
@LyftAPI._register_patch("book_ride", "fixedfare")
def book_ride_fixedfare(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    requested_type = kwargs.get("ride_type_id")
    if requested_type is None and len(args) >= 5:
        requested_type = args[4]
    if requested_type != "standard":
        return result
    ride_id = result["ride_id"]
    result["fare_total"] = 30.0
    if ride_id in self.rides:
        self.rides[ride_id]["fare_total"] = 30.0
    return result


# ---------- book_ride (partial commit) ----------


# ft_extra_50 -- corrupted_state/temporary. The first call appears to
# succeed (returns a ride record) but the persisted ride row is left in
# an intermediate state with status='pending_payment' rather than the
# normal 'matched' / 'requested' status, signaling that the payment
# authorization didn't fully commit. The list-rides view will surface the
# half-baked row. Second call fully succeeds.
@LyftAPI._register_patch("book_ride", "partial_commit_pending_payment_temporary")
def book_ride_partial_commit_pending_payment_temporary(self, *args, **kwargs):
    """Temporary corruption. First call leaves the persisted ride with
    status='pending_payment' and stamps a 'partial_commit' marker. The
    response also reflects the suspicious status so the agent can detect
    via list_rides or by inspecting the return. Second call falls through."""
    if self._patch_call_count <= 1:
        result = self._original_function(*args, **kwargs)
        ride_id = result.get("ride_id")
        result["status"] = "pending_payment"
        result["partial_commit"] = True
        if ride_id and ride_id in self.rides:
            self.rides[ride_id]["status"] = "pending_payment"
            self.rides[ride_id]["partial_commit"] = True
        return result
    return self._original_function(*args, **kwargs)


# ─── Source: yash (alternate-path blockers) ───

@LyftAPI._register_patch("schedule_ride", "blocked")
def schedule_ride_blocked(self, *args, **kwargs):
    raise LyftError("FEATURE_DISABLED", "")

@LyftAPI._register_patch("list_trip_history", "blocked")
def list_trip_history_blocked(self, *args, **kwargs):
    raise LyftError("FEATURE_DISABLED", "")
