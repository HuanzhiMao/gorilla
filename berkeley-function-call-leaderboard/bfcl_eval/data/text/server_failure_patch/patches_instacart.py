"""Runtime patches for InstacartAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.instacart import InstacartAPI

# ─── Source: patches_instacart.py ───


@InstacartAPI._register_patch("get_grocery_cart", "CORRUPTED_NULL_ITEMS_PERMANENT")
def patch_cart_corrupted(self, cart_id):
    cart = self._original_function(cart_id)
    cart['items'] = [
        {'product_id': 'IC-DAUD-1001', 'quantity': 1, 'price': -1.0, 'product_name': 'NULL_REF_ERROR'},
        {'product_id': 'IC-DAUD-1002', 'quantity': 2, 'price': -1.0, 'product_name': 'NULL_REF_ERROR'},
    ]
    cart['subtotal'] = -300
    cart['corrupted_state'] = True
    return cart


@InstacartAPI._register_patch("get_grocery_cart", "STALE_SAVED_CART_PERMANENT")
def patch_stale_saved_cart(self, cart_id):
    cart = self._original_function(cart_id)
    cart['last_synced_at'] = '2026-03-20T09:00:00Z'
    cart['inventory_verified'] = False
    cart['stale_snapshot'] = True
    return cart


@InstacartAPI._register_patch("checkout", "LEGACY_ADDRESS_CORRUPTION_ON_LEGACY_CART")
def patch_checkout_corruption(self, cart_id, address_id, payment_method_id, delivery_window_id, tip=200):
    order_id = self._original_function(cart_id, address_id, payment_method_id, delivery_window_id, tip)
    if cart_id == 'IC-33921':
        self.orders[order_id]['address_id'] = 'addr_old_999'
        self.orders[order_id]['payment_method_id'] = 'pm_expired_0012'
    return order_id


@InstacartAPI._register_patch("get_order_status", "EXPOSE_ADDRESS_AND_PAYMENT")
def patch_order_status_details(self, order_id):
    status = self._original_function(order_id)
    order = self.orders.get(order_id, {})
    status['address_id'] = order.get('address_id')
    status['payment_method_id'] = order.get('payment_method_id')
    return status
