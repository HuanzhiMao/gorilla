"""Runtime patches for ExpediaAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.expedia import ExpediaAPI, ExpediaError
from datetime import datetime

# ─── Source: patches_expedia.py ───


# ---------- create_booking ----------

# ft_004 -- service unavailable
@ExpediaAPI._register_patch("create_itinerary", "unavailable")
def create_itinerary_unavailable(self, *args, **kwargs):
    raise ExpediaError(
        "SERVICE_UNAVAILABLE",
        "Expedia booking service is currently unavailable for this property.",
    )


# ft_006 -- nightly rate mismatch (total != nightly_rate * nights)
@ExpediaAPI._register_patch("create_itinerary", "nightlyratemismatch")
def create_itinerary_nightlyratemismatch(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    booking_id = result["booking_id"]
    check_in = kwargs.get("check_in_date", args[1] if len(args) > 1 else "2026-12-20")
    check_out = kwargs.get("check_out_date", args[2] if len(args) > 2 else "2026-12-25")
    try:
        nights = max(1, (datetime.fromisoformat(check_out) - datetime.fromisoformat(check_in)).days)
    except (ValueError, TypeError):
        nights = 5
    nightly_rate = 720.0
    bad_total = round(nightly_rate * nights * 1.05, 2)
    result["total_price"] = bad_total
    result["rate_breakdown_for_total_price"] = {
        "nightly_rate": nightly_rate,
        "nights": nights,
        "subtotal_note": "Standard rate applied"
    }
    if booking_id in self.bookings:
        self.bookings[booking_id]["total_price"] = bad_total
        self.bookings[booking_id]["rate_breakdown_for_total_price"] = result["rate_breakdown_for_total_price"]
    return result


# ---------- modify_booking ----------

# ft_006 -- blocked (prevent alternate path)
@ExpediaAPI._register_patch("update_itinerary", "blocked")
def update_itinerary_blocked(self, *args, **kwargs):
    raise ExpediaError(
        "FEATURE_DISABLED",
        "Booking modifications are not available for this property. Please try a different approach.",
    )


# ---------- create_itinerary (price_breakdown_partial_commit_permanent) ----------


# ft_extra_57 -- corrupted_state/permanent. The itinerary is created
# successfully but the persisted price_breakdown is left half-populated:
# the room subtotal is correct but the taxes/fees field is null and the
# total_price field is set to just the room subtotal (i.e. taxes never
# committed). The agent must spot the missing taxes by inspecting the
# itinerary post-create and warn the user / re-quote the trip.
@ExpediaAPI._register_patch("create_itinerary", "price_breakdown_partial_commit_permanent")
def create_itinerary_price_breakdown_partial_commit_permanent(self, *args, **kwargs):
    """Permanent. Persists the itinerary then nulls taxes/fees and rolls
    back total_price to room_subtotal so the booking under-reports cost.
    Returns the corrupted result so the agent can spot it directly."""
    result = self._original_function(*args, **kwargs)
    booking_id = result.get("booking_id") or result.get("itinerary_id")
    # Best-effort: if the underlying booking exists, mutate it; always mutate
    # the returned dict so the caller sees the corruption.
    target = result
    if booking_id and booking_id in getattr(self, "bookings", {}):
        target = self.bookings[booking_id]
    breakdown = target.get("rate_breakdown_for_total_price") or target.get("price_breakdown") or {}
    room_subtotal = breakdown.get("nightly_rate", 0)
    nights = breakdown.get("nights", 1)
    if isinstance(room_subtotal, (int, float)) and isinstance(nights, int):
        new_total = round(room_subtotal * nights, 2)
        target["total_price"] = new_total
        result["total_price"] = new_total
    if isinstance(target.get("price_breakdown"), dict):
        target["price_breakdown"]["taxes"] = None
        target["price_breakdown"]["fees"] = None
    target["partial_price_commit"] = True
    result["partial_price_commit"] = True
    return result
