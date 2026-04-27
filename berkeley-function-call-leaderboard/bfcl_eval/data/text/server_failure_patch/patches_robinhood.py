"""Runtime patches for RobinhoodAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.robinhood import (
    RobinhoodAPI,
    RobinhoodError,
)

# ============================================================================
# Patches below, grouped by method, with scenario ID comments
# ============================================================================

# ---------- get_crypto_portfolio ----------

# ft_021 -- BTC value shifted to tiny amount
@RobinhoodAPI._register_patch("get_crypto_portfolio", "valueshift")
def get_crypto_portfolio_valueshift(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    if "BTC" in result.get("holdings", {}):
        result["holdings"]["BTC"]["current_value"] = 156.37
        total = 0.0
        for sym, holding in result["holdings"].items():
            total += holding.get("current_value", 0.0)
        result["total_value"] = round(total, 2)
    return result


# ---------- place_options_order ----------


# ft_extra_25 -- First call rejects with a transient SCHEMA_MISMATCH error
# claiming a new 'contract_symbol' field is required (a staging-side schema
# rollout that hasn't been documented yet). Second call falls through to the
# original implementation. Agent must retry once.
@RobinhoodAPI._register_patch("place_options_order", "contract_symbol_schema_temporary")
def place_options_order_contract_symbol_schema_temporary(self, *args, **kwargs):
    """Temporary. The first invocation raises a SCHEMA_MISMATCH error naming
    'contract_symbol' as a required field; subsequent invocations succeed.
    Mirrors VanguardAPI.execute_rebalance/schema_strict_ack_token_temporary."""
    if self._patch_call_count <= 1:
        raise RobinhoodError(
            error_code="SCHEMA_MISMATCH",
            message=(
                "Request validation failed: field 'contract_symbol' is "
                "required in the new options-order schema."
            ),
            suggested_action=(
                "Retry without changes -- the gateway will resolve the "
                "contract symbol from (symbol, option_type, strike_price, "
                "expiration_date) on the next attempt during the rollout window."
            ),
            context={"schema_version": "options_v3"},
        )
    return self._original_function(*args, **kwargs)


# ---------- setup_recurring_investment ----------


# ft_extra_26 -- First call hits a maintenance window for the recurring-
# investment scheduler subsystem; surfaces a retryable MAINTENANCE_WINDOW
# error and the second call falls through to the original implementation.
@RobinhoodAPI._register_patch("setup_recurring_investment", "maintenance_window_temporary")
def setup_recurring_investment_maintenance_window_temporary(self, *args, **kwargs):
    """Temporary. First invocation raises MAINTENANCE_WINDOW with a clear
    retryable hint; second invocation falls through and persists normally."""
    if self._patch_call_count <= 1:
        raise RobinhoodError(
            error_code="MAINTENANCE_WINDOW",
            message=(
                "Recurring-investment scheduler is in a brief maintenance "
                "window; this call was not persisted."
            ),
            suggested_action=(
                "Retry the same request -- the maintenance window is short "
                "(under a minute) and a second attempt should succeed."
            ),
            context={"retryable": True, "subsystem": "recurring_scheduler"},
        )
    return self._original_function(*args, **kwargs)


# ---------- get_dividends ----------


# ft_extra_89 -- get_dividends first call drops every entry whose pay_date
# falls in 2024-Q4 (a stale-index regression hides 2 of 6 dividends). Second
# call falls through to the real list. Recovery: retry once and reconcile.
@RobinhoodAPI._register_patch("get_dividends", "missing_q4_temporary")
def get_dividends_missing_q4_temporary(self, *args, **kwargs):
    """Temporary data_staleness. First invocation filters out any dividend
    whose pay_date starts with 2024-12; second invocation returns the full
    list via the original implementation. Recovery: spot the count
    mismatch and retry."""
    if self._patch_call_count <= 1:
        real = self._original_function(*args, **kwargs)
        return [d for d in real if not str(d.get("pay_date", "")).startswith("2024-12")]
    return self._original_function(*args, **kwargs)

