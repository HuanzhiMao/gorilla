"""Runtime patches for UberEatsAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.uber_eats import UberEatsError, UberEatsAPI
from datetime import datetime, timezone, timedelta
import uuid

def _arg(args, kwargs, idx, name, default=None):
    if name in kwargs:
        return kwargs[name]
    return args[idx] if len(args) > idx else default


# ─── Source: socrates ───


@UberEatsAPI._register_patch("submit_food_order", "phantom_permanent")
def submit_food_order_phantom_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake order_id without ever placing the order.
    The order never exists in the system, so get_order / cancel_order will correctly fail."""
    return f"order_{uuid.uuid4().hex[:8]}"


@UberEatsAPI._register_patch("search_restaurants", "stale_permanent")
def search_restaurants_stale_permanent(self, *args, **kwargs):
    """Permanent. Calls original, modifies results to mark all restaurants as open
    and sets last_updated to 4 months ago. Some restaurants may actually be closed."""
    results = self._original_function(*args, **kwargs)
    stale_date = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    for restaurant in results:
        restaurant["is_open"] = True
        restaurant["last_updated"] = stale_date
    return results


@UberEatsAPI._register_patch("submit_food_order", "unavailable_permanent")
def submit_food_order_unavailable_permanent(self, *args, **kwargs):
    """Permanent. Always raises SERVICE_UNAVAILABLE."""
    raise UberEatsError("SERVICE_UNAVAILABLE", "")


# ─── Source: yash ───


# ft_022 -- doubled total
@UberEatsAPI._register_patch("submit_food_order", "doubledtotal")
def submit_food_order_doubledtotal(self, *args, **kwargs):
    order_id = self._original_function(*args, **kwargs)
    if order_id in self.orders:
        self.orders[order_id]["total"] = round(self.orders[order_id]["total"] * 2, 2)
    return order_id


# ─── Source: yuxuan ───


# S51: Late night pizza — Night Owl closed on UE
@UberEatsAPI._register_patch("submit_food_order", "s51_restaurant_closed")
def submit_food_order_s51_restaurant_closed(self, *args, **kwargs):
    restaurant_id = _arg(args, kwargs, 0, "restaurant_id")
    if restaurant_id == "night_owl_01":
        raise UberEatsError(
            error_code="RESTAURANT_CLOSED",
            message="Restaurant is currently closed.",
            suggested_action="Choose another restaurant or try again during open hours.",
            context={"restaurant_id": restaurant_id},
        )
    return self._original_function(*args, **kwargs)


# S52: Poker night — nachos out of stock on UE
@UberEatsAPI._register_patch("submit_food_order", "s52_nachos_out_of_stock")
def submit_food_order_s52_nachos_out_of_stock(self, *args, **kwargs):
    items = _arg(args, kwargs, 1, "items", [])
    if any((it or {}).get("item_id") == "pb_nachos" for it in (items or [])):
        raise UberEatsError(
            error_code="ITEM_UNAVAILABLE",
            message="Item 'pb_nachos' is out of stock.",
            suggested_action="Choose a different item from get_menu().",
            context={"item_id": "pb_nachos"},
        )
    return self._original_function(*args, **kwargs)


# S53: Post-gym — out of delivery zone on UE
@UberEatsAPI._register_patch("submit_food_order", "s53_out_of_zone")
def submit_food_order_s53_out_of_zone(self, *args, **kwargs):
    raise UberEatsError(
        error_code="OUT_OF_DELIVERY_ZONE",
        message="Delivery address is outside the maximum delivery radius.",
        suggested_action="Use a closer address or select another restaurant.",
        context={"max_radius_miles": 5.0},
    )


# S54: Anniversary dinner — payments outage
@UberEatsAPI._register_patch("submit_food_order", "s54_payments_outage_temporary")
def submit_food_order_s54_payments_outage_temporary(self, *args, **kwargs):
    if self._patch_call_count <= 2:
        raise UberEatsError(
            error_code="PAYMENTS_OUTAGE",
            message="Payment processing is currently unavailable.",
            suggested_action="Retry with backoff.",
            context={},
        )
    return self._original_function(*args, **kwargs)


# S55: Thai food — promo SPICY15 not eligible at bangkok_st on UE
@UberEatsAPI._register_patch("submit_food_order", "s55_promo_not_eligible")
def submit_food_order_s55_promo_not_eligible(self, *args, **kwargs):
    restaurant_id = _arg(args, kwargs, 0, "restaurant_id")
    offer_id = _arg(args, kwargs, 5, "offer_id")
    if (
        (offer_id or "").upper() in ("SPICY15", "SPINSTACART15", "SPINSTACART_Y15")
        and restaurant_id == "bangkok_st"
    ):
        raise UberEatsError(
            error_code="OFFER_NOT_IN_WALLET",
            message=f"Offer '{offer_id}' is not in your promo wallet.",
            suggested_action="Only offers in your promo wallet can be applied.",
            context={"offer_id": offer_id},
        )
    return self._original_function(*args, **kwargs)


# S57: Wrong order report + restaurant closed on reorder
@UberEatsAPI._register_patch("submit_food_order", "s57_sakura_closed")
def submit_food_order_s57_sakura_closed(self, *args, **kwargs):
    restaurant_id = _arg(args, kwargs, 0, "restaurant_id")
    if restaurant_id == "sakura_01":
        raise UberEatsError(
            error_code="RESTAURANT_CLOSED",
            message="Restaurant is currently closed.",
            suggested_action="Choose another restaurant or try again during open hours.",
            context={"restaurant_id": restaurant_id},
        )
    return self._original_function(*args, **kwargs)


# S60: Seoul Crunchy empty menu on UE
@UberEatsAPI._register_patch("get_menu", "s60_empty_menu")
def get_menu_s60_empty_menu(self, restaurant_id):
    if restaurant_id == "seoul_crunchy":
        return []
    return self._original_function(restaurant_id)


# S61: Group order — no default payment method
@UberEatsAPI._register_patch("submit_food_order", "s61_no_default_payment")
def submit_food_order_s61_no_default_payment(self, *args, **kwargs):
    raise UberEatsError(
        error_code="NO_DEFAULT_PAYMENT_METHOD",
        message="Organizer has no default payment method.",
        suggested_action="Add a valid default payment method first.",
        context={"organizer_user_id": self.user_id},
    )


# S63: Split order — guac out of stock on UE
@UberEatsAPI._register_patch("submit_food_order", "s63_guac_out_of_stock")
def submit_food_order_s63_guac_out_of_stock(self, *args, **kwargs):
    items = _arg(args, kwargs, 1, "items", [])
    if any((it or {}).get("item_id") == "guac_dip" for it in (items or [])):
        raise UberEatsError(
            error_code="ITEM_UNAVAILABLE",
            message="Item 'guac_dip' is out of stock.",
            suggested_action="Choose a different item from get_menu().",
            context={"item_id": "guac_dip"},
        )
    return self._original_function(*args, **kwargs)


# S64: Promo applied but $0 discount in order details (silent corruption)
@UberEatsAPI._register_patch("get_order", "s64_promo_discount_zero")
def get_order_s64_promo_discount_zero(self, order_id):
    result = self._original_function(order_id)
    if isinstance(result.get("applied_promo"), dict):
        result["applied_promo"]["discount"] = 0.0
    return result


# Alternate-path FEATURE_DISABLED patches (per Yash #3).
# These force the model down the intended must_be_called path by disabling
# semantically equivalent shortcuts that would bypass the real failure injection.

# S61/110: force submit_food_order (intended) by disabling finalize_group_order
@UberEatsAPI._register_patch("finalize_group_order", "s61_alt_finalize_disabled")
def finalize_group_order_s61_alt_disabled(self, *args, **kwargs):
    raise UberEatsError(error_code="FEATURE_DISABLED", message="")


# S61/110: force submit_food_order (intended) by disabling schedule_order
@UberEatsAPI._register_patch("schedule_order", "s61_alt_schedule_disabled")
def schedule_order_s61_alt_disabled(self, *args, **kwargs):
    raise UberEatsError(error_code="FEATURE_DISABLED", message="")


# ---------- schedule_order (silent_noop_permanent) ----------


# ft_extra_52 -- silent_noop/permanent. schedule_order returns a fake
# scheduled_order_id and a 'scheduled' status payload, but no row is
# persisted to self.scheduled_orders. The order will never actually fire.
# Agent must verify by listing scheduled orders or fetching the returned
# id and flag the failure.
import uuid as _uuid
from datetime import datetime as _datetime, timezone as _timezone


@UberEatsAPI._register_patch("schedule_order", "scheduled_order_noop_permanent")
def schedule_order_scheduled_order_noop_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns a scheduled_order_id-shaped payload
    without persisting anything. A follow-up read for the id will fail."""
    fake_id = f"sched_order_{_uuid.uuid4().hex[:8]}"
    now = _datetime.now(_timezone.utc).isoformat()
    return {
        "scheduled_order_id": fake_id,
        "status": "scheduled",
        "created_at": now,
    }


# ---------- schedule_order (temporary) ----------


# ft_extra_97 -- schedule_order first call raises SCHEDULE_QUEUE_OVERLOAD
# (a retryable availability_denial). Second call falls through to the real
# implementation. Recovery: retry once.
@UberEatsAPI._register_patch("schedule_order", "schedule_queue_overload_temporary")
def schedule_order_schedule_queue_overload_temporary(self, *args, **kwargs):
    """Temporary availability_denial. First invocation raises
    SCHEDULE_QUEUE_OVERLOAD with retry_after_seconds. Second invocation
    falls through. Recovery: retry once."""
    if self._patch_call_count <= 1:
        from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.uber_eats import UberEatsError
        raise UberEatsError(
            error_code="SCHEDULE_QUEUE_OVERLOAD",
            message="Scheduling queue is briefly saturated; please retry shortly.",
            suggested_action="Retry after the retry_after_seconds window.",
            context={"retryable": True, "retry_after_seconds": 8},
        )
    return self._original_function(*args, **kwargs)


# ─── Source: yash (alternate-path blockers) ───

@UberEatsAPI._register_patch("finalize_group_order", "blocked")
def finalize_group_order_blocked(self, *args, **kwargs):
    raise UberEatsError(error_code="FEATURE_DISABLED", message="")

@UberEatsAPI._register_patch("get_restaurant", "blocked")
def get_restaurant_blocked(self, *args, **kwargs):
    raise UberEatsError(error_code="FEATURE_DISABLED", message="")

@UberEatsAPI._register_patch("get_order_history", "blocked")
def get_order_history_blocked(self, *args, **kwargs):
    raise UberEatsError(error_code="FEATURE_DISABLED", message="")

@UberEatsAPI._register_patch("track_order", "blocked")
def track_order_blocked(self, *args, **kwargs):
    raise UberEatsError(error_code="FEATURE_DISABLED", message="")
