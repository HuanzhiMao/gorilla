"""Runtime patches for LyftAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.lyft import LyftAPI, LyftError

# ─── Source: patches_lyft.py ───


# ---------- get_ride_estimates ----------

# ft_012 -- fare breakdown mismatch
@LyftAPI._register_patch("get_ride_estimates", "breakdownmismatch")
def get_ride_estimates_breakdownmismatch(self, *args, **kwargs):
    results = self._original_function(*args, **kwargs)
    if results:
        results[0]["estimated_fare"] = 18.0
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
@LyftAPI._register_patch("book_ride", "capacityviolation")
def book_ride_capacityviolation(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    ride_id = result["ride_id"]
    result["ride_type_id"] = "xl"
    result["capacity"] = 4
    if ride_id in self.rides:
        self.rides[ride_id]["ride_type_id"] = "xl"
        self.rides[ride_id]["capacity"] = 4
    return result


# ft_020 -- fixed fare override (Lyft side of cross-platform scenario)
@LyftAPI._register_patch("book_ride", "fixedfare")
def book_ride_fixedfare(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
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
