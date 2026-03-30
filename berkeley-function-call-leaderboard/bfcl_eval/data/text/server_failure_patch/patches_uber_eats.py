"""Runtime patches for UberEatsOrderAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.uber_eats import UberEatsError, UberEatsOrderAPI
from datetime import datetime, timezone, timedelta
import uuid

def _arg(args, kwargs, idx, name, default=None):
    if name in kwargs:
        return kwargs[name]
    return args[idx] if len(args) > idx else default


# ─── Source: socrates ───


@UberEatsOrderAPI._register_patch("place_order", "phantom_permanent")
def place_order_phantom_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake order_id without ever placing the order.
    The order never exists in the system, so get_order / cancel_order will correctly fail."""
    return f"order_{uuid.uuid4().hex[:8]}"


@UberEatsOrderAPI._register_patch("search_restaurants", "stale_permanent")
def search_restaurants_stale_permanent(self, *args, **kwargs):
    """Permanent. Calls original, modifies results to mark all restaurants as open
    and sets last_updated to 4 months ago. Some restaurants may actually be closed."""
    results = self._original_function(*args, **kwargs)
    stale_date = (datetime.now(timezone.utc) - timedelta(days=120)).isoformat()
    for restaurant in results:
        restaurant["is_open"] = True
        restaurant["last_updated"] = stale_date
    return results


@UberEatsOrderAPI._register_patch("place_order", "unavailable_permanent")
def place_order_unavailable_permanent(self, *args, **kwargs):
    """Permanent. Always raises SERVICE_UNAVAILABLE."""
    raise PatchError(
        "SERVICE_UNAVAILABLE",
        "UberEats ordering service is temporarily offline.",
        "Try DoorDash or another delivery service.",
    )


# ─── Source: yash ───


# ft_022 -- doubled total
@UberEatsOrderAPI._register_patch("place_order", "doubledtotal")
def ft022_place_order_doubledtotal(self, *args, **kwargs):
    order_id = self._original_function(*args, **kwargs)
    if order_id in self.orders:
        self.orders[order_id]["total"] = round(self.orders[order_id]["total"] * 2, 2)
    return order_id


# ─── Source: yuxuan ───


# S51: Late night pizza — Night Owl closed on UE
@UberEatsOrderAPI._register_patch("place_order", "s51_restaurant_closed")
def s51_place_order(self, *args, **kwargs):
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
@UberEatsOrderAPI._register_patch("place_order", "s52_nachos_out_of_stock")
def s52_place_order(self, *args, **kwargs):
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
@UberEatsOrderAPI._register_patch("place_order", "s53_out_of_zone")
def s53_place_order(self, *args, **kwargs):
    raise UberEatsError(
        error_code="OUT_OF_DELIVERY_ZONE",
        message="Delivery address is outside the maximum delivery radius.",
        suggested_action="Use a closer address or select another restaurant.",
        context={"max_radius_miles": 5.0},
    )


# S54: Anniversary dinner — payments outage
@UberEatsOrderAPI._register_patch("place_order", "s54_payments_outage_temporary")
def s54_place_order(self, *args, **kwargs):
    if self._patch_call_count <= 2:
        raise UberEatsError(
            error_code="PAYMENTS_OUTAGE",
            message="Payment processing is currently unavailable.",
            suggested_action="Retry with backoff.",
            context={},
        )
    return self._original_function(*args, **kwargs)


# S55: Thai food — promo SPICY15 not eligible at bangkok_st on UE
@UberEatsOrderAPI._register_patch("place_order", "s55_promo_not_eligible")
def s55_place_order(self, *args, **kwargs):
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
@UberEatsOrderAPI._register_patch("place_order", "s57_sakura_closed")
def s57_place_order(self, *args, **kwargs):
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
@UberEatsOrderAPI._register_patch("get_menu", "s60_empty_menu")
def s60_get_menu(self, restaurant_id):
    if restaurant_id == "seoul_crunchy":
        return []
    return self._original_function(restaurant_id)


# S61: Group order — no default payment method
@UberEatsOrderAPI._register_patch("place_order", "s61_no_default_payment")
def s61_place_order(self, *args, **kwargs):
    raise UberEatsError(
        error_code="NO_DEFAULT_PAYMENT_METHOD",
        message="Organizer has no default payment method.",
        suggested_action="Add a valid default payment method first.",
        context={"organizer_user_id": self.user_id},
    )


# S63: Split order — guac out of stock on UE
@UberEatsOrderAPI._register_patch("place_order", "s63_guac_out_of_stock")
def s63_place_order(self, *args, **kwargs):
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
@UberEatsOrderAPI._register_patch("get_order", "s64_promo_discount_zero")
def s64_get_order(self, order_id):
    result = self._original_function(order_id)
    if isinstance(result.get("applied_promo"), dict):
        result["applied_promo"]["discount"] = 0.0
    return result
