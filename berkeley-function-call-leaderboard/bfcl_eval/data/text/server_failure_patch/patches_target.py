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
