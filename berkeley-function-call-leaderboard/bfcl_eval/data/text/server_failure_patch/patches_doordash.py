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
def place_dash_s58_payment_not_found(self, *args, **kwargs):
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
def reorder_s59_pho_saigon_closed(self, *args, **kwargs):
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
def place_dash_s62_restaurant_rejected_persistent(self, *args, **kwargs):
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
def place_dash_s63_partial_stock_only_guac(self, *args, **kwargs):
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


# Alternate-path FEATURE_DISABLED patch (per Yash #3).
# S56/105: force the cancel + place_dash flow by disabling reorder shortcut.
@DoorDashAPI._register_patch("reorder", "s56_alt_reorder_disabled")
def reorder_s56_alt_disabled(self, *args, **kwargs):
    raise DoorDashError(
        error_code="FEATURE_DISABLED",
        message="One-tap reorder is disabled for this account.",
        suggested_action="Place a new order using place_dash.",
        context={},
    )


# ---------- place_dash (tip schema migration) ----------


# ft_extra_51 -- schema_mismatch/permanent. The DoorDash tipping API has
# rolled out a v2 schema that requires tip be expressed as an integer
# cents value with a 'tip_cents' parameter, instead of the legacy float
# 'tip' (dollars). Until the client-side SDK is rebuilt this rejects with
# SCHEMA_MIGRATION_REQUIRED. Permanent.
@DoorDashAPI._register_patch("place_dash", "tip_schema_migration_permanent")
def place_dash_tip_schema_migration_permanent(self, *args, **kwargs):
    """Permanent. Always raises SCHEMA_MIGRATION_REQUIRED naming
    'tip_cents' as the required field. Agent should NOT keep retrying;
    pivot to UberEats or warn the user."""
    raise DoorDashError(
        error_code="SCHEMA_MIGRATION_REQUIRED",
        message=(
            "place_dash rejected: legacy float 'tip' is no longer accepted; "
            "the v2 API requires integer cents in 'tip_cents'."
        ),
        suggested_action=(
            "Do NOT retry with the same payload -- the rollout requires a "
            "client-side schema change. Pivot to an alternate platform or "
            "warn the user."
        ),
        context={"schema_version": "place_dash_v2"},
    )


# ─── Source: yash (alternate-path blockers) ───

@DoorDashAPI._register_patch("reorder", "blocked")
def reorder_blocked(self, *args, **kwargs):
    raise DoorDashError(error_code="FEATURE_DISABLED")

@DoorDashAPI._register_patch("send_gift_order", "blocked")
def send_gift_order_blocked(self, *args, **kwargs):
    raise DoorDashError(error_code="FEATURE_DISABLED")

@DoorDashAPI._register_patch("get_store_details", "blocked")
def get_store_details_blocked(self, *args, **kwargs):
    raise DoorDashError(error_code="FEATURE_DISABLED")

@DoorDashAPI._register_patch("get_dash_history", "blocked")
def get_dash_history_blocked(self, *args, **kwargs):
    raise DoorDashError(error_code="FEATURE_DISABLED")
