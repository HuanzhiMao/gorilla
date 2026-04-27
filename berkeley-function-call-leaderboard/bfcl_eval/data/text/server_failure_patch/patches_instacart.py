"""Runtime patches for InstacartAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.instacart import (
    InstacartAPI,
    InstacartError,
)
from copy import deepcopy

# ─── Source: patches_instacart.py ───


@InstacartAPI._register_patch("get_grocery_cart", "corrupted_null_items_permanent")
def get_grocery_cart_corrupted_null_items_permanent(self, cart_id):
    cart = self._original_function(cart_id)
    cart['items'] = [
        {'product_id': 'IC-DAUD-1001', 'quantity': 1, 'price': -1.0, 'product_name': 'NULL_REF_ERROR'},
        {'product_id': 'IC-DAUD-1002', 'quantity': 2, 'price': -1.0, 'product_name': 'NULL_REF_ERROR'},
    ]
    cart['subtotal'] = -300
    cart['corrupted_state'] = True
    return cart


@InstacartAPI._register_patch("get_grocery_cart", "stale_saved_cart_permanent")
def get_grocery_cart_stale_saved_cart_permanent(self, cart_id):
    cart = self._original_function(cart_id)
    cart['last_synced_at'] = '2026-03-20T09:00:00Z'
    cart['inventory_verified'] = False
    cart['stale_snapshot'] = True
    return cart


@InstacartAPI._register_patch("checkout", "legacy_address_corruption_on_legacy_cart")
def checkout_legacy_address_corruption_on_legacy_cart(self, cart_id, address_id, payment_method_id, delivery_window_id, tip=200):
    order_id = self._original_function(cart_id, address_id, payment_method_id, delivery_window_id, tip)
    if cart_id == 'IC-33921':
        self.orders[order_id]['address_id'] = 'addr_old_999'
        self.orders[order_id]['payment_method_id'] = 'pm_expired_0012'
    return order_id


@InstacartAPI._register_patch("get_order_status", "expose_address_and_payment")
def get_order_status_expose_address_and_payment(self, order_id):
    status = self._original_function(order_id)
    order = self.orders.get(order_id, {})
    status['address_id'] = order.get('address_id')
    status['payment_method_id'] = order.get('payment_method_id')
    return status


# ---------- get_delivery_slots ----------


# ft_extra_30 -- corrupted_state/permanent. The slot ISO timestamps are
# stamped with year 2025 instead of 2026 due to a year-rollover off-by-one
# bug in the slot generator. Returned 'available=true' is honest, but the
# 'start' / 'end' fields point at a year in the past so booking would fail
# downstream. Agent must spot the year mismatch and warn the user before
# committing to a slot.
@InstacartAPI._register_patch("get_delivery_slots", "year_off_by_one_permanent")
def get_delivery_slots_year_off_by_one_permanent(self, store_id, *args, **kwargs):
    """Permanent silent corruption. Every returned window has its 'start'
    and 'end' ISO timestamps shifted back by one year (2026 -> 2025). The
    slot IDs and 'available' flags are unchanged."""
    windows = self._original_function(store_id, *args, **kwargs)
    out = []
    for w in windows:
        cw = deepcopy(w)
        for f in ("start", "end"):
            v = cw.get(f, "")
            if isinstance(v, str) and v.startswith("2026"):
                cw[f] = "2025" + v[4:]
        out.append(cw)
    return out


# ---------- checkout ----------


# ft_extra_31 -- data_staleness/temporary. The first call hits a cached
# tax-rate table that is roughly two months stale, inflating the order
# total by ~3% (cents-precise). The second call falls through to the
# fresh implementation. Agent must notice the order_status total is off
# vs the cart subtotal+fees+tip and retry.
@InstacartAPI._register_patch("checkout", "stale_tax_rate_temporary")
def checkout_stale_tax_rate_temporary(
    self, cart_id, address_id, payment_method_id, delivery_window_id, tip=200, *args, **kwargs
):
    """Temporary. First call writes the order with a tax field inflated by
    a stale-cache factor (1.03). Second and later calls fall through to the
    original implementation. The cart row is unchanged so a retry produces
    a clean order."""
    if self._patch_call_count <= 1:
        order_id = self._original_function(
            cart_id, address_id, payment_method_id, delivery_window_id, tip
        )
        order = self.orders.get(order_id, {})
        # Inflate the recorded tax + total to mimic a stale rate
        prior_tax = order.get("tax_cents", 0)
        prior_total = order.get("total_cents", order.get("total", 0))
        bonus = int(round(prior_tax * 0.03)) if prior_tax else int(round(prior_total * 0.01))
        if "tax_cents" in order:
            order["tax_cents"] = prior_tax + bonus
        if "total_cents" in order:
            order["total_cents"] = prior_total + bonus
        elif "total" in order:
            order["total"] = prior_total + bonus
        order["_stale_tax_warning"] = True
        return order_id
    return self._original_function(
        cart_id, address_id, payment_method_id, delivery_window_id, tip
    )


# ---------- add_recipe_to_cart ----------


# ft_extra_90 -- silent_noop/permanent. The recipe-to-cart bridge appears
# to succeed but the unmatched ingredients list is silently emptied -- the
# response claims everything matched even when several ingredients did not
# resolve to store inventory. The matched array reflects only what was
# actually added. Permanent: client SDK is dropping the unmatched array.
@InstacartAPI._register_patch("add_recipe_to_cart", "drop_unmatched_silent_permanent")
def add_recipe_to_cart_drop_unmatched_silent_permanent(self, cart_id, recipe_id, servings=None, *args, **kwargs):
    """Permanent silent corruption. The original method runs; afterwards we
    blank the `unmatched` array in the response so the caller believes
    everything was added. Recovery: cross-check by fetching the recipe via
    get_recipe(recipe_id) and the cart via get_grocery_cart(cart_id), then
    compare the ingredient list against the cart items to find the missing
    ones."""
    real = self._original_function(cart_id, recipe_id, servings)
    real["unmatched"] = []
    real["_unmatched_warning"] = "unmatched array suppressed by client SDK"
    return real

