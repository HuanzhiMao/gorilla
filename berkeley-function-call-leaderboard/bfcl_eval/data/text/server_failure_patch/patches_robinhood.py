"""Runtime patches for RobinhoodAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.robinhood import RobinhoodAPI

# ============================================================================
# Patches below, grouped by method, with scenario ID comments
# ============================================================================

# ---------- get_crypto_portfolio ----------

# ft_021 -- BTC value shifted to tiny amount
@RobinhoodAPI._register_patch("get_crypto_portfolio", "valueshift")
def ft021_get_crypto_portfolio_valueshift(self, *args, **kwargs):
    result = self._original_function(*args, **kwargs)
    if "BTC" in result.get("holdings", {}):
        result["holdings"]["BTC"]["current_value"] = 156.37
        total = 0.0
        for sym, holding in result["holdings"].items():
            total += holding.get("current_value", 0.0)
        result["total_value"] = round(total, 2)
    return result
