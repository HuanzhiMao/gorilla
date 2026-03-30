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
            {'slot_id': 'WMT-SLOT-CACHE-001', 'date': '2026-03-27', 'start_time': '08:00', 'end_time': '09:00', 'available': False},
            {'slot_id': 'WMT-SLOT-CACHE-002', 'date': '2026-03-27', 'start_time': '09:00', 'end_time': '10:00', 'available': False},
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
