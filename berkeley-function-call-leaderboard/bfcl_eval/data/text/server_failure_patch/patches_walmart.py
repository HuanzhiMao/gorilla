"""Runtime patches for WalmartAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.walmart import WalmartAPI, WalmartError

# ─── Source: daud ───


@WalmartAPI._register_patch("add_item_to_basket", "schema_422_permanent")
def add_item_to_basket_schema_422_permanent(self, product_id, quantity, fulfillment_type=None, store_id=None, substitution_pref=None):
    raise WalmartError(
        error_code='UNPROCESSABLE_ENTITY',
        message='422 request validation error: fulfillment_option must now be a nested object instead of a flat fulfillment_type field.',
        suggested_action='Use another retailer if this schema mismatch persists.',
        context={'product_id': product_id},
    )


@WalmartAPI._register_patch("get_pickup_slots", "stale_no_slots_once")
def get_pickup_slots_stale_no_slots_once(self, store_id):
    if self._patch_call_count == 1:
        return [
            {
                'slot_id': 'WMT-SLOT-CACHE-001',
                'date': '2026-03-27',
                'start_time': '08:00',
                'end_time': '09:00',
                'available': False,
                'cache_status': 'stale',
                'last_refreshed_at': '2026-03-25T07:30:00Z',
            },
            {
                'slot_id': 'WMT-SLOT-CACHE-002',
                'date': '2026-03-27',
                'start_time': '09:00',
                'end_time': '10:00',
                'available': False,
                'cache_status': 'stale',
                'last_refreshed_at': '2026-03-25T07:30:00Z',
            },
        ]
    return self._original_function(store_id)


# ─── Source: yash ───


# ft_025 -- ready_at override
@WalmartAPI._register_patch("get_purchase_details", "readyat")
def get_purchase_details_readyat(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    result["ready_at"] = "2026-04-15T18:00:00-05:00"
    return result


# ft_025 -- all slots before ready time
@WalmartAPI._register_patch("get_pickup_slots", "allbeforeready")
def get_pickup_slots_allbeforeready(self, *args, **kwargs):
    return [
        {"slot_id": "slot_early_1", "date": "2026-04-15", "start_time": "08:00", "end_time": "09:00", "available": True},
        {"slot_id": "slot_early_2", "date": "2026-04-15", "start_time": "10:00", "end_time": "11:00", "available": True},
        {"slot_id": "slot_early_3", "date": "2026-04-15", "start_time": "14:00", "end_time": "15:00", "available": True}
    ]


# ---------- check_price_match ----------


# ft_extra_35 -- data_staleness/temporary. The first call returns a
# competitor-price-match decision computed from a stale competitor cache
# (no_match=true even when a real match exists). Second call falls through
# to the fresh implementation. Agent must retry to get the real match
# decision before applying the discount.
@WalmartAPI._register_patch("check_price_match", "stale_competitor_cache_temporary")
def check_price_match_stale_competitor_cache_temporary(self, product_id, *args, **kwargs):
    """Temporary. First call returns a 'no match found' response sourced
    from a stale competitor-price cache. Second call falls through to the
    original implementation."""
    if self._patch_call_count <= 1:
        return {
            "product_id": product_id,
            "match_found": False,
            "matched_price_cents": None,
            "matched_competitor": None,
            "cache_age_days": 18,
            "cache_status": "stale",
        }
    return self._original_function(product_id, *args, **kwargs)


# ---------- get_pickup_slots (service_degraded_empty_temporary) ----------


# ft_extra_59 -- availability_denial/temporary. First call returns an
# empty list with a service_degraded marker (the slot service is in a
# brief brownout). Second call falls through and returns real slots.
@WalmartAPI._register_patch("get_pickup_slots", "service_degraded_empty_temporary")
def get_pickup_slots_service_degraded_empty_temporary(self, store_id, *args, **kwargs):
    """Temporary. First call returns an empty list (signaling no slots,
    misleadingly). Second call falls through to the real implementation,
    which returns the configured slot list."""
    if self._patch_call_count <= 1:
        return []
    return self._original_function(store_id, *args, **kwargs)


# ─── Source: yash (alternate-path blockers) ───


@WalmartAPI._register_patch("submit_order", "blocked")
def submit_order_blocked(self, *args, **kwargs):
    raise WalmartError("FEATURE_DISABLED", "")
