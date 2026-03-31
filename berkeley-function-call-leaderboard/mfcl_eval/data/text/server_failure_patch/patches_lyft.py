"""Runtime patches for LyftAPI methods."""

from mfcl_eval.eval_checker.multi_turn_eval.func_source_code.lyft import LyftAPI

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
