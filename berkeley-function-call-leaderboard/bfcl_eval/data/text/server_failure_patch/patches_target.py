"""Runtime patches for TargetAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.target import TargetAPI, TargetError
from copy import deepcopy

# ─── Source: daud ───


@TargetAPI._register_patch("check_in_store_availability", "region_denied_permanent")
def check_in_store_availability_region_denied_permanent(self, product_id, store_id):
    raise TargetError(
        error_code='REGION_UNAVAILABLE',
        message='503 Service Unavailable: region-specific fulfillment is unavailable for zip 30309 and no retry window was provided.',
        suggested_action='Use another delivery platform serving the same region.',
        context={'product_id': product_id, 'store_id': store_id},
    )


@TargetAPI._register_patch("put_in_cart", "region_denied_permanent")
def put_in_cart_region_denied_permanent(self, product_id, quantity, fulfillment_type=None, store_id=None):
    raise TargetError(
        error_code='REGION_UNAVAILABLE',
        message='503 Service Unavailable: Target cannot fulfill this product in the requested region.',
        suggested_action='Use another delivery platform serving the same region.',
        context={'product_id': product_id, 'store_id': store_id},
    )


# ─── Source: yash ───


# ft_026 -- RedCard discount glitch (0.5% instead of 5%)
@TargetAPI._register_patch("checkout_order", "redcardglitch")
def checkout_order_redcardglitch(self, *args, **kwargs):
    cart_snapshot = deepcopy(self.cart)
    result = self._original_function(*args, **kwargs)
    order_id = result["order_id"]
    subtotal = result["subtotal"]
    bad_discount = int(round(subtotal * 0.005))
    delta = result["redcard_discount"] - bad_discount
    result["redcard_discount"] = bad_discount
    result["redcard_discount_should_be_5_percent"] = True
    result["total"] += delta
    if order_id in self.orders:
        self.orders[order_id]["redcard_discount"] = bad_discount
        self.orders[order_id]["redcard_discount_should_be_5_percent"] = True
        self.orders[order_id]["total"] += delta
    self.cart = cart_snapshot
    return result


# ---------- apply_circle_offer ----------


# ft_extra_32 -- schema_mismatch/permanent. The Circle offer engine has
# rolled out a v2 schema that requires a 'circle_offer_v2_token' qualifier
# on the request. Until the client SDK is updated this call permanently
# fails with SCHEMA_MIGRATION_REQUIRED. Agent must NOT keep retrying;
# pivot to apply_discount_code with the equivalent legacy promo code, or
# warn the user the Circle offer cannot be applied right now.
@TargetAPI._register_patch("apply_circle_offer", "offer_schema_v2_required_permanent")
def apply_circle_offer_offer_schema_v2_required_permanent(self, offer_id, *args, **kwargs):
    """Permanent. Every call raises SCHEMA_MIGRATION_REQUIRED. The error is
    explicitly NOT retryable -- the suggested_action notes that the legacy
    v1 schema has been retired and only a server-side rollout fixes it."""
    raise TargetError(
        error_code="SCHEMA_MIGRATION_REQUIRED",
        message=(
            "Circle offer apply rejected: required field "
            "'circle_offer_v2_token' missing. The v1 offer-apply schema has "
            "been retired and the v2 client SDK is not yet rolled out."
        ),
        suggested_action=(
            "Do NOT retry -- this will not self-heal. Use "
            "apply_discount_code with an equivalent legacy promo code, or "
            "tell the user the Circle offer cannot be applied right now."
        ),
        context={"offer_id": offer_id, "schema_version": "circle_v2"},
    )


# ---------- get_circle_points ----------


# ft_extra_88 -- get_circle_points returns a stale points_balance from
# before recent purchases were posted. lifetime_earnings is correct
# (independent feed) so the discrepancy is detectable. Permanent.
@TargetAPI._register_patch("get_circle_points", "points_balance_stale_permanent")
def get_circle_points_points_balance_stale_permanent(self, *args, **kwargs):
    """Permanent data_staleness. Returns points_balance from a snapshot
    taken before recent earnings posted, while lifetime_earnings reflects
    the live total. The two fields therefore disagree (lifetime > balance
    by the missing increment). Recovery: notice lifetime_earnings >
    points_balance + redeemed_to_date and warn the user the balance is
    behind."""
    membership = self.profile.get("membership", {})
    if not membership.get("circle_member", False):
        return {
            "circle_member": False,
            "points_balance": 0,
            "lifetime_earnings": 0,
            "next_reward_threshold": 0,
        }
    real_points = membership.get("circle_points", 0)
    lifetime = membership.get("lifetime_circle_earnings", real_points)
    # Subtract a stale offset so balance lags lifetime by ~1500 points
    stale_balance = max(0, real_points - 1500)
    next_threshold = 5000 - (stale_balance % 5000) if stale_balance % 5000 != 0 else 0
    return {
        "circle_member": True,
        "points_balance": stale_balance,
        "lifetime_earnings": lifetime,
        "next_reward_threshold": next_threshold,
        "snapshot_at": "2026-03-30T00:00:00Z",
        "data_freshness": "stale",
    }
