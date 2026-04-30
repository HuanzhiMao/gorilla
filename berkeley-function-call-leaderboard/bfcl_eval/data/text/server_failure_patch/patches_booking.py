"""Runtime patches for BookingAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.booking import BookingAPI, BookingError
from copy import deepcopy
from datetime import datetime, timezone
import uuid

# ─── Source: socrates ─────────────────────────────────────────────────────────


@BookingAPI._register_patch("create_booking", "noop_permanent")
def create_booking_noop_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake booking confirmation without ever creating it.
    The booking never exists, so get_booking will correctly fail."""
    now = datetime.now(timezone.utc).isoformat()
    booking_id = f"booking_{uuid.uuid4().hex[:8]}"
    return {
        "booking_id": booking_id,
        "property_id": kwargs.get("property_id", ""),
        "room_type_id": kwargs.get("room_type_id", ""),
        "guest_info": kwargs.get("guest_info", {}),
        "check_in_date": kwargs.get("check_in_date", ""),
        "check_out_date": kwargs.get("check_out_date", ""),
        "num_guests": kwargs.get("num_guests", 1),
        "rooms_booked": kwargs.get("rooms", 1),
        "total_price": 0.0,
        "payment_status": "paid",
        "booking_status": "confirmed",
        "created_at": now,
        "updated_at": now,
    }


@BookingAPI._register_patch("create_booking", "room_unavailable")
def create_booking_room_unavailable(self, *args, **kwargs):
    """Permanent. Always raises ROOM_UNAVAILABLE."""
    raise BookingError(
        "ROOM_UNAVAILABLE",
        "The selected room is no longer available. Cached availability was stale.",
        "Search for alternative rooms or try a different hotel.",
    )


# ─── Source: yash ─────────────────────────────────────────────────────────────


# ft_001 -- price mismatch with fake discount breakdown
@BookingAPI._register_patch("create_booking", "pricemismatch")
def create_booking_pricemismatch(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    booking_id = result["booking_id"]
    bad_total = 88000
    breakdown = {"loyalty_discount": 2500, "promo_discount": 1000}
    result["total_price"] = bad_total
    result["discount_breakdown"] = deepcopy(breakdown)
    result["discount_note"] = "Special multi-night savings applied"
    if booking_id in self.bookings:
        self.bookings[booking_id]["total_price"] = bad_total
        self.bookings[booking_id]["discount_breakdown"] = deepcopy(breakdown)
        self.bookings[booking_id]["discount_note"] = result["discount_note"]
    return result


# ft_005 -- discount glitch inflates total
@BookingAPI._register_patch("create_booking", "discountglitch")
def create_booking_discountglitch(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    booking_id = result["booking_id"]
    bad_total = 332500
    result["total_price"] = bad_total
    result["genius_discount"] = "15% loyalty discount applied"
    if booking_id in self.bookings:
        self.bookings[booking_id]["total_price"] = bad_total
        self.bookings[booking_id]["genius_discount"] = result["genius_discount"]
    return result


# ft_008 -- room swap to wrong room type
@BookingAPI._register_patch("create_booking", "roomswap")
def create_booking_roomswap(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    reservation_id = result["booking_id"]
    result["room_id"] = "ROOM-008A"
    result["assigned_room_name"] = "Deluxe Double Room"
    result["max_guests"] = 2
    if reservation_id in self.bookings:
        self.bookings[reservation_id]["room_id"] = "ROOM-008A"
        self.bookings[reservation_id]["assigned_room_name"] = "Deluxe Double Room"
        self.bookings[reservation_id]["max_guests"] = 2
    return result


# ft_009 -- persistent wrong dates/guests (Feb 11-14, 1 guest)
@BookingAPI._register_patch("create_booking", "dateguestpersistent009")
def create_booking_dateguestpersistent009(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    reservation_id = result["booking_id"]
    result["check_in_date"] = "2026-02-11"
    result["check_out_date"] = "2026-02-14"
    result["num_guests"] = 1
    if reservation_id in self.bookings:
        self.bookings[reservation_id]["check_in_date"] = "2026-02-11"
        self.bookings[reservation_id]["check_out_date"] = "2026-02-14"
        self.bookings[reservation_id]["num_guests"] = 1
    return result


# ft_010 -- persistent wrong dates/guests (Dec 21-24, 1 guest)
@BookingAPI._register_patch("create_booking", "dateguestpersistent010")
def create_booking_dateguestpersistent010(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    reservation_id = result["booking_id"]
    result["check_in_date"] = "2026-12-21"
    result["check_out_date"] = "2026-12-24"
    result["num_guests"] = 1
    if reservation_id in self.bookings:
        self.bookings[reservation_id]["check_in_date"] = "2026-12-21"
        self.bookings[reservation_id]["check_out_date"] = "2026-12-24"
        self.bookings[reservation_id]["num_guests"] = 1
    return result


# ft_011 -- ghost write (booking deleted from store after creation)
@BookingAPI._register_patch("create_booking", "ghostwrite")
def create_booking_ghostwrite(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    reservation_id = result["booking_id"]
    if reservation_id in self.bookings:
        del self.bookings[reservation_id]
    return result


# ft_002 -- capacity-bypass: returns properties ignoring guest count
@BookingAPI._register_patch("search_properties", "capbypass002")
def search_properties_capbypass002(self, *args, **kwargs):
    city = kwargs.get("city", args[0] if args else "")
    limit = kwargs.get("limit", 20)
    results = []
    for prop in self.properties.values():
        prop_city = prop.get("location", {}).get("city", prop.get("city", ""))
        if city.strip().lower() not in prop_city.lower():
            continue
        prices = [
            rt.get("base_price_per_night", rt.get("price_per_night", 0))
            for rt in self.room_types.values()
            if rt.get("property_id") == prop["property_id"]
        ]
        if not prices:
            continue
        item = deepcopy(prop)
        item["cheapest_price_per_night"] = min(prices)
        results.append(item)
    return results[:limit]


# ft_007 -- capacity-bypass for hostels
@BookingAPI._register_patch("search_properties", "capbypass007")
def search_properties_capbypass007(self, *args, **kwargs):
    city = kwargs.get("city", args[0] if args else "")
    limit = kwargs.get("limit", 20)
    results = []
    for prop in self.properties.values():
        prop_city = prop.get("location", {}).get("city", prop.get("city", ""))
        if city.strip().lower() not in prop_city.lower():
            continue
        prices = [
            rt.get("base_price_per_night", rt.get("price_per_night", 0))
            for rt in self.room_types.values()
            if rt.get("property_id") == prop["property_id"]
        ]
        item = deepcopy(prop)
        item["cheapest_price_per_night"] = min(prices) if prices else 0
        results.append(item)
    return results[:limit]


# ft_003 -- refund contradiction
@BookingAPI._register_patch("cancel_booking", "refundcontradiction")
def cancel_booking_refundcontradiction(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    result["refund_amount"] = 17500
    result["free_cancellation"] = False
    return result


# ft_001/ft_005/ft_008/ft_009/ft_010 -- blocked (identical implementations)
@BookingAPI._register_patch("modify_booking", "blocked")
def modify_booking_blocked(self, *args, **kwargs):
    raise BookingError("FEATURE_DISABLED", "")


# ft_001/ft_005/ft_008/ft_009 -- blocked (identical implementations)
@BookingAPI._register_patch("get_property", "blocked")
def get_property_blocked(self, *args, **kwargs):
    raise BookingError("FEATURE_DISABLED", "")


# ---------- modify_booking (regional date format) ----------


# ft_extra_37 -- schema_mismatch/permanent. The modify_booking endpoint
# rejects ISO YYYY-MM-DD dates with INVALID_DATE_FORMAT and demands the
# regional DD/MM/YYYY format for this property's locale (an undocumented
# rollout for EU-region inventory). Permanent in this scenario; agent
# should pivot to cancel_booking + create_booking on the alternate
# platform (Expedia) rather than spinning on the rejection.
@BookingAPI._register_patch("modify_booking", "regional_date_format_permanent")
def modify_booking_regional_date_format_permanent(self, booking_id, *args, **kwargs):
    """Permanent. Always raises INVALID_DATE_FORMAT naming the regional
    DD/MM/YYYY format; the error is explicitly NOT retryable until the
    rollout completes."""
    raise BookingError(
        "INVALID_DATE_FORMAT",
        (
            "Date format rejected: this property's locale requires "
            "DD/MM/YYYY for modify_booking. The ISO YYYY-MM-DD format is "
            "not accepted in the new EU schema."
        ),
        "Do NOT retry with the same dates. Cancel and rebook on an alternate "
        "platform if the modification is essential.",
    )


# ---------- cancel_booking ----------


# ft_extra_98 -- cancel_booking returns an inflated refund_amount that
# does not match the original total_price. The underlying booking is
# correctly marked cancelled, but the refund figure is wrong (a stale
# fee table caused the refund engine to over-credit). Permanent: the fee
# table is upstream and only fixes itself on the next platform deploy.
@BookingAPI._register_patch("cancel_booking", "refund_inflated_permanent")
def cancel_booking_refund_inflated_permanent(self, booking_id, *args, **kwargs):
    """Permanent corrupted_state. The booking is correctly cancelled but
    the returned refund_amount is the original total_price * 1.4 -- an
    inflated number that does not reconcile with the booking total.
    Recovery: cross-check by reading get_booking(booking_id) and notice
    the refund_amount > total_price, then warn the user before relying
    on the inflated refund."""
    real = self._original_function(booking_id, *args, **kwargs)
    refund = real.get("refund_amount", 0)
    if refund:
        real["refund_amount"] = round(refund * 1.4, 2)
        real["_refund_table_warning"] = "refund total may not match booking total_price"
    return real


# ─── Source: yash (alternate-path blockers) ───


@BookingAPI._register_patch("list_bookings", "blocked")
def list_bookings_blocked(self, *args, **kwargs):
    raise BookingError("FEATURE_DISABLED", "")


@BookingAPI._register_patch("apply_genius_discount", "blocked")
def apply_genius_discount_blocked(self, *args, **kwargs):
    raise BookingError("FEATURE_DISABLED", "")


@BookingAPI._register_patch("get_genius_deals", "blocked")
def get_genius_deals_blocked(self, *args, **kwargs):
    raise BookingError("FEATURE_DISABLED", "")
