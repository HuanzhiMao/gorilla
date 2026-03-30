"""Runtime patches for AmazonAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.amazon import AmazonAPI, AmazonError

# ─── Source: daud ─────────────────────────────────────────────────────────────


@AmazonAPI._register_patch("add_to_cart", "ADD_TO_CART_503_PERMANENT")
def patch_add_to_cart_503(self, product_id, quantity, variant_id=None, seller_id=None, gift_wrap=False, gift_message=None):
    raise AmazonError(
        error_code='SERVICE_UNAVAILABLE',
        message='503 Service Unavailable: High traffic, please retry.',
        suggested_action='Retry once if appropriate or use another retailer.',
        context={'product_id': product_id},
    )


@AmazonAPI._register_patch("get_cart", "GHOST_ITEMS_PERMANENT")
def patch_get_cart_ghost(self):
    cart = self._original_function()
    cart['ghost_order_reference'] = 'AMZ-9918'
    cart['subtotal'] = 34782
    cart['unexpected_items_present'] = True
    return cart


@AmazonAPI._register_patch("apply_coupon", "CART_CORRUPTED_PERMANENT")
def patch_coupon_corrupted(self, coupon_code):
    raise AmazonError(
        error_code='CART_CORRUPTED',
        message='Coupon application failed because the current cart contains corrupted legacy line items.',
        suggested_action='Abandon this cart and rebuild the purchase on another retailer.',
        context={'coupon_code': coupon_code},
    )


@AmazonAPI._register_patch("get_product_offers", "NESTED_OFFERS_ONCE")
def patch_nested_offers(self, product_id):
    offers = self._original_function(product_id)
    if self._patch_call_count == 1 and product_id == 'AMZ-DAUD-1006':
        primary = offers[0]
        return {
            'product_id': product_id,
            'selected_offer': {
                'seller_id': primary['seller_id'],
                'offer_token': 'algorithms_offer_v2',
                'price': {'display': '$109.99', 'amount_cents': primary['price']},
            },
            'fallback_offers': offers[1:],
        }
    return offers


@AmazonAPI._register_patch("add_to_cart", "SELLER_REQUIRED_ONCE")
def patch_seller_required(self, product_id, quantity, variant_id=None, seller_id=None, gift_wrap=False, gift_message=None):
    if self._patch_call_count == 1 and product_id == 'AMZ-DAUD-1006' and not seller_id:
        raise AmazonError(
            error_code='UNPROCESSABLE_ENTITY',
            message='422 Unprocessable Entity: seller_id is now required when adding this product after the offer schema migration.',
            suggested_action='Inspect the offer payload again and retry with a valid seller_id.',
            context={'product_id': product_id},
        )
    return self._original_function(product_id, quantity, variant_id, seller_id, gift_wrap, gift_message)


@AmazonAPI._register_patch("add_to_cart", "SILENT_REPLICATION_LAG_ONCE")
def patch_replication_lag(self, product_id, quantity, variant_id=None, seller_id=None, gift_wrap=False, gift_message=None):
    if self._patch_call_count == 1:
        return {
            'status': 'success',
            'product_id': product_id,
            'quantity_added': quantity,
            'message': 'Item replicated to cart.',
        }
    return self._original_function(product_id, quantity, variant_id, seller_id, gift_wrap, gift_message)


# ─── Source: socrates ─────────────────────────────────────────────────────────


@AmazonAPI._register_patch("place_order", "session_expired")
def place_order_session_expired(self, *args, **kwargs):
    """Permanent. Calls original, modifies result to indicate session expiration,
    and removes the order from state. Returns corrupted response."""
    order_id = self._original_function(*args, **kwargs)
    # Remove the order from state since it was not actually processed
    if order_id in self.orders:
        del self.orders[order_id]
    # Return a corrupted response dict instead of the order_id string
    return {
        "order_id": order_id,
        "status": "session_expired",
        "error_detail": "Your session has expired. The order was not processed.",
    }


# ─── Source: yash ─────────────────────────────────────────────────────────────


# ft_027 -- service unavailable
@AmazonAPI._register_patch("add_to_cart", "unavailable")
def ft027_add_to_cart_unavailable(self, *args, **kwargs):
    raise AmazonError(
        "SERVICE_UNAVAILABLE",
        "Amazon add_to_cart is unavailable for this product.",
    )
