"""Runtime patches for DoorDashAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.doordash import DoorDashAPI, DoorDashError

# ─── Source: patches_doordash.py ───


def _arg(args, kwargs, idx, name, default=None):
    if name in kwargs:
        return kwargs[name]
    return args[idx] if len(args) > idx else default


# ============================================================================
# S58: El Fuego burrito — DD has no payment methods
# Trigger: place_order fails with PAYMENT_METHOD_NOT_FOUND
# Note: Can also be achieved purely via initial state (payment_methods=[])
# ============================================================================
@DoorDashAPI._register_patch("place_dash", "s58_payment_not_found")
def s58_place_dash(self, *args, **kwargs):
    payment_method_id = _arg(args, kwargs, 3, "payment_method_id")
    raise DoorDashError(
        error_code="PAYMENT_METHOD_NOT_FOUND",
        message=f"Payment method '{payment_method_id}' not found for user.",
        suggested_action="Call list_payment_methods() to get valid method IDs.",
        context={"user_id": self.user_id, "method_id": payment_method_id},
    )


# ============================================================================
# S59: Pho Saigon — closed on DD reorder
# Trigger: reorder fails because restaurant is closed
# ============================================================================
@DoorDashAPI._register_patch("reorder", "s59_pho_saigon_closed")
def s59_reorder(self, *args, **kwargs):
    raise DoorDashError(
        error_code="RESTAURANT_CLOSED",
        message="Restaurant is currently closed.",
        suggested_action="Choose another restaurant or try again during open hours.",
        context={"restaurant_id": "pho_saigon"},
    )


# ============================================================================
# S62: Sal's Pizza — persistent RESTAURANT_REJECTED on DD
# Trigger: place_order always fails
# ============================================================================
@DoorDashAPI._register_patch("place_dash", "s62_restaurant_rejected_persistent")
def s62_place_dash(self, *args, **kwargs):
    raise DoorDashError(
        error_code="RESTAURANT_REJECTED",
        message="Restaurant failed to confirm the order.",
        suggested_action="Retry later or choose another restaurant.",
        context={"restaurant_id": "sals_ny_pizza"},
    )


# ============================================================================
# S63: Split order — wings/mozz/potato out of stock on DD
# Trigger: place_order fails if any item other than guac_dip is requested
# ============================================================================
@DoorDashAPI._register_patch("place_dash", "s63_partial_stock_only_guac")
def s63_place_dash(self, *args, **kwargs):
    items = _arg(args, kwargs, 1, "items", [])
    available_items = {"guac_dip"}
    bad_items = [
        (it or {}).get("item_id")
        for it in (items or [])
        if (it or {}).get("item_id") not in available_items
    ]
    if bad_items:
        raise DoorDashError(
            error_code="ITEM_OUT_OF_STOCK",
            message=f"Item '{bad_items[0]}' is out of stock.",
            suggested_action="Choose a different item from get_menu().",
            context={"item_id": bad_items[0]},
        )
    return self._original_function(*args, **kwargs)
