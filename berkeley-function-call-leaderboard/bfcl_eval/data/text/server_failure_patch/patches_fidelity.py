"""Runtime patches for FidelityAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.fidelity import (
    FidelityAPI,
    FidelityError,
)
import uuid
from copy import deepcopy

# ============================================================================
# Patches below, grouped by method, with scenario ID comments
# ============================================================================

# ---------- set_stock_alert ----------


# ft_extra_23 -- set_stock_alert returns a fake alert_id but never writes
# to self.stock_alerts. list_stock_alerts / get alert flow will not find it.
@FidelityAPI._register_patch("set_stock_alert", "alert_write_noop_permanent")
def set_stock_alert_alert_write_noop_permanent(self, symbol, condition, threshold, *args, **kwargs):
    """Permanent silent no-op. Fidelity's alerts subsystem returns a success
    payload but the write never makes it to the durable alerts table; the
    user will never receive the alert. Agent must verify via list_stock_alerts
    and flag the miss."""
    return {
        "alert_id": f"stock_alert_{uuid.uuid4().hex[:8]}",
        "symbol": symbol.upper(),
        "condition": condition,
        "threshold": threshold,
        "status": "active",
    }


# ---------- get_tax_lots ----------


# ft_extra_24 -- On the first call this returns each lot twice (double-count
# bug in the lot aggregator). Retry within the same session returns the
# correct list; the symptom is transient.
@FidelityAPI._register_patch("get_tax_lots", "lot_double_count_temporary")
def get_tax_lots_lot_double_count_temporary(self, symbol, *args, **kwargs):
    """Temporary. First invocation returns every matching lot twice with
    inflated gain_loss values, which would make a sell-for-tax-loss
    recommendation dangerously wrong. Second invocation returns the correct
    list from the original implementation."""
    if self._patch_call_count <= 1:
        real = self._original_function(symbol, *args, **kwargs)
        doubled = []
        for lot in real:
            doubled.append(deepcopy(lot))
            dup = deepcopy(lot)
            # mark the duplicate with a suffix so it's technically distinguishable
            # but easy to double-count in aggregate
            dup["lot_id"] = f"{lot.get('lot_id')}_dup"
            dup["shares"] = lot.get("shares", 0)
            # gain_loss also doubles because shares are untouched
            doubled.append(dup)
        return doubled
    return self._original_function(symbol, *args, **kwargs)


# ---------- create_basket ----------


# ft_extra_84 -- create_basket appears to succeed but durable state is
# written with renormalized weights that no longer match the user's
# intent (a stale weight-validation rule rebases everything to equal
# weights). Permanent silent corruption.
@FidelityAPI._register_patch("create_basket", "weight_renormalization_corruption_permanent")
def create_basket_weight_renormalization_corruption_permanent(self, name, securities, *args, **kwargs):
    """Permanent silent corruption. Stores the basket with weights flattened
    to equal-weight regardless of the user's input, but echoes the user's
    requested weights back in the response. Recovery: cross-check via
    get_basket(basket_id) and notice every weight became 100/N."""
    # Validate inputs minimally (mimicking the real method's checks)
    if not securities:
        raise FidelityError("EMPTY_BASKET", "Securities list cannot be empty.")
    total_weight = sum(s.get("weight_percent", 0) for s in securities)
    if abs(total_weight - 100) > 0.01:
        raise FidelityError(
            "INVALID_WEIGHTS",
            f"Weights must sum to 100, got {total_weight}.",
            context={"total_weight": total_weight},
        )
    for s in securities:
        self._require_stock(s.get("symbol", ""))

    n = len(securities)
    flat = round(100.0 / n, 4)
    flattened = []
    for s in securities:
        flattened.append({
            "symbol": s.get("symbol", "").upper(),
            "weight_percent": flat,
        })
    basket_id = self._new_id("basket")
    from datetime import datetime, timezone
    self.baskets[basket_id] = {
        "basket_id": basket_id,
        "name": name,
        "securities": deepcopy(flattened),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Misleading echo: the response shows the user's *requested* weights
    return {
        "basket_id": basket_id,
        "name": name,
        "securities": deepcopy(securities),
        "status": "active",
    }


# ---------- get_research_report ----------


# ft_extra_85 -- get_research_report returns a stale research snapshot
# whose target_price was set 9 months ago and is now lower than the
# current_price. Recommendation field is stale "buy" but the target is
# already exceeded. Permanent: research feed is on a long refresh cycle.
@FidelityAPI._register_patch("get_research_report", "outdated_target_price_permanent")
def get_research_report_outdated_target_price_permanent(self, symbol, *args, **kwargs):
    """Permanent data_staleness. Returns a research report whose target_price
    is below the current_price and whose published_at is 9 months stale.
    Recovery: compare report.target_price against the live get_stock_quote
    price; if target<current and recommendation='buy', flag as stale."""
    sym = symbol.upper()
    real = self._original_function(symbol, *args, **kwargs)
    out = deepcopy(real)
    quote = self.portfolio.get(sym, {})
    current = quote.get("current_price", out.get("target_price", 0))
    # Drop target_price below current to make the staleness obvious
    out["target_price"] = round(current * 0.78, 2) if current else 0
    out["published_at"] = "2025-07-12T00:00:00Z"
    out["data_freshness"] = "stale"
    return out


# ---------- trade_basket ----------


# ft_extra_86 -- trade_basket on first invocation only places orders for
# half of the basket's securities (a partial-commit bug in the basket
# trade splitter). Second invocation falls through to a clean execution.
@FidelityAPI._register_patch("trade_basket", "partial_basket_fill_temporary")
def trade_basket_partial_basket_fill_temporary(self, basket_id, total_amount, side, *args, **kwargs):
    """Temporary corrupted_state. First call only places orders for the
    first half of the basket securities (partial commit). Order_ids list
    therefore short-counts. Second call falls through to the original
    implementation. Recovery: count order_ids vs basket security_count
    and retry if short."""
    if self._patch_call_count <= 1:
        basket = self.baskets.get(basket_id)
        if not basket:
            raise FidelityError("BASKET_NOT_FOUND", f"Basket '{basket_id}' not found.")
        if basket.get("status") != "active":
            raise FidelityError("BASKET_INACTIVE", "Basket is not active.")
        if side not in ("buy", "sell"):
            raise FidelityError("INVALID_SIDE", "Side must be 'buy' or 'sell'.")
        if total_amount <= 0:
            raise FidelityError("INVALID_AMOUNT", "Amount must be positive.")
        secs = basket.get("securities", [])
        # Only place orders for the first half (rounded down)
        keep = max(1, len(secs) // 2)
        partial_basket = deepcopy(secs[:keep])
        order_ids = []
        for s in partial_basket:
            sym = s.get("symbol", "").upper()
            weight = s.get("weight_percent", 0) / 100.0
            alloc = total_amount * weight
            sec = self.portfolio.get(sym, {})
            price = sec.get("current_price", 1)
            qty = round(alloc / price, 6)
            if qty > 0:
                result = self.place_order(sym, side, qty, order_type="market")
                order_ids.append(result["order_id"])
        return {
            "basket_id": basket_id,
            "side": side,
            "total_amount": total_amount,
            "order_ids": order_ids,
            "_partial_commit": True,
        }
    return self._original_function(basket_id, total_amount, side, *args, **kwargs)


# ---------- get_analyst_rating ----------


# ft_extra_87 -- get_analyst_rating returns the inverted recommendation
# (buy<->sell, hold unchanged). Permanent corrupted_state. Recovery:
# cross-check against get_research_report.recommendation, which uses an
# independent feed.
@FidelityAPI._register_patch("get_analyst_rating", "rating_inverted_permanent")
def get_analyst_rating_rating_inverted_permanent(self, symbol, *args, **kwargs):
    """Permanent corrupted_state. The analyst_rating buy/sell labels are
    swapped before returning. Hold remains hold. Recovery: cross-check
    against get_research_report (independent feed) or the underlying
    portfolio quote's analyst_rating."""
    real = self._original_function(symbol, *args, **kwargs)
    out = deepcopy(real)
    rating = (out.get("analyst_rating") or "").lower()
    if rating == "buy":
        out["analyst_rating"] = "sell"
    elif rating == "sell":
        out["analyst_rating"] = "buy"
    out["_rating_feed_warning"] = "rating polarity may be inverted"
    return out
