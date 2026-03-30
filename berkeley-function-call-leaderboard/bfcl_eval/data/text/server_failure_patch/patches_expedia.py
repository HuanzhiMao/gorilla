"""Runtime patches for ExpediaAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.expedia import ExpediaAPI, ExpediaError
from datetime import datetime

# ─── Source: patches_expedia.py ───


# ---------- create_booking ----------

# ft_004 -- service unavailable
@ExpediaAPI._register_patch("create_itinerary", "unavailable")
def ft004_create_itinerary_unavailable(self, *args, **kwargs):
    raise ExpediaError(
        "SERVICE_UNAVAILABLE",
        "Expedia booking service is currently unavailable for this property.",
    )


# ft_006 -- nightly rate mismatch (total != nightly_rate * nights)
@ExpediaAPI._register_patch("create_itinerary", "nightlyratemismatch")
def ft006_create_itinerary_nightlyratemismatch(self, *args, **kwargs):
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
def ft006_update_itinerary_blocked(self, *args, **kwargs):
    raise ExpediaError(
        "FEATURE_DISABLED",
        "Booking modifications are not available for this property. Please try a different approach.",
    )
