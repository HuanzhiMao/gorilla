"""
Fidelity Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Single-profile brokerage: stock/ETF/mutual fund trading, analyst research,
  fund screening, watchlist, and tax lot tracking.
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .server_patch_mixin import PatchableMixin


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class FidelityError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        suggested_action: str = "",
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.error = {
            "error_code": error_code,
            "message": message,
            "suggested_action": suggested_action,
            "context": context or {},
        }

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self.error)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _matches_query(text: str, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    return q in (text or "").lower()


DEFAULT_STATE = {
    "random_seed": 6002,
    "profile": {},
    "portfolio": {},
    "positions": {},
    "orders": {},
    "watchlist": {},
    "tax_lots": {},
}


class FidelityAPI(PatchableMixin):
    """
    In-memory dummy implementation of a Fidelity-like brokerage.

    Supports a single user profile with stock/ETF/mutual fund trading,
    analyst ratings, fund screening, a watchlist, and tax lot tracking.
    """


    def __init__(self):
        self._id_counters = {"order": 0, "tax_lot": 0}
        self.profile: Dict[str, Any]
        self.portfolio: Dict[str, Dict[str, Any]]
        self.positions: Dict[str, Dict[str, Any]]
        self.orders: Dict[str, Dict[str, Any]]
        self.watchlist: List[str]
        self.tax_lots: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Fidelity brokerage API, which provides "
            "investment management, stock/ETF/mutual fund trading, "
            "analyst research, fund screening, and tax lot tracking."
        )


    def _new_id(self, prefix: str) -> str:
        """Generate the next sequential ID for *prefix* (e.g. ``order_1``)."""
        self._id_counters[prefix] = self._id_counters.get(prefix, 0) + 1
        return f"{prefix}_{self._id_counters[prefix]}"

    def _load_scenario(
        self,
        scenario: Dict[str, Any],
        long_context: bool = False,
    ) -> None:
        """
        Load a scenario from the scenarios folder.
        Args:
            scenario (Dict[str, Any]): The scenario to load
        """
        DEFAULT_STATE_COPY = deepcopy(DEFAULT_STATE)
        self._random = random.Random(
            scenario.get("random_seed", DEFAULT_STATE_COPY["random_seed"])
        )
        self.profile = scenario.get("profile", DEFAULT_STATE_COPY["profile"])
        self.portfolio = scenario.get("portfolio", DEFAULT_STATE_COPY["portfolio"])
        self.positions = scenario.get("positions", DEFAULT_STATE_COPY["positions"])
        self.orders = scenario.get("orders", DEFAULT_STATE_COPY["orders"])
        self.watchlist = scenario.get("watchlist", DEFAULT_STATE_COPY["watchlist"])
        self.tax_lots = scenario.get("tax_lots", DEFAULT_STATE_COPY["tax_lots"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, FidelityAPI):
            return False

        for attr_name in vars(self):
            if attr_name.startswith("_"):
                continue
            model_attr = getattr(self, attr_name)
            ground_truth_attr = getattr(value, attr_name)

            if model_attr != ground_truth_attr:
                return False

        return True

    # -----------------------------------------------------------------------
    # Internal mechanics
    # -----------------------------------------------------------------------

    def _require_stock(self, symbol: str) -> Dict[str, Any]:
        """Look up a security in the portfolio by symbol."""
        entry = self.portfolio.get(symbol.upper())
        if not entry:
            raise FidelityError(
                "SECURITY_NOT_FOUND",
                f"Security '{symbol}' not found.",
                suggested_action="Use search_stocks() to find valid symbols.",
            )
        return entry

    def _require_order(self, order_id: str) -> Dict[str, Any]:
        order = self.orders.get(order_id)
        if not order:
            raise FidelityError(
                "ORDER_NOT_FOUND",
                f"Order '{order_id}' not found.",
                suggested_action="Use list_orders() to find valid order IDs.",
            )
        return order

    # -----------------------------------------------------------------------
    # User profile
    # -----------------------------------------------------------------------

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get the current user's profile.

        Returns:
            Dict[str, Any]: name, email, account_type, buying_power, cash_balance.
        """
        return deepcopy(self.profile)

    # -----------------------------------------------------------------------
    # Securities & research
    # -----------------------------------------------------------------------

    def get_stock_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get a detailed quote for a security.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: symbol, name, type, current_price, day_change,
                day_change_percent, bid, ask, tradable, market_open, and any
                additional fields present in the portfolio entry.
        """
        return deepcopy(self._require_stock(symbol))

    def search_stocks(
        self, query: str, security_type: Optional[str] = None, limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for stocks, ETFs, and mutual funds.

        Args:
            query (str): Search text matched against name and symbol.
            security_type (str, optional): Filter by type -- "stock", "etf",
                "option", "crypto", or "mutual_fund".
            limit (int): Max results. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Matching securities from the portfolio.
        """
        results = []
        for s in self.portfolio.values():
            if security_type and s.get("type") != security_type:
                continue
            if _matches_query(s.get("name", ""), query) or _matches_query(s.get("symbol", ""), query):
                results.append(deepcopy(s))
        return results[:limit]

    def get_analyst_rating(self, symbol: str) -> Dict[str, Any]:
        """
        Get analyst rating details for a security.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: symbol (str), analyst_rating (str buy/hold/sell),
                target_price (float), sector (str).
        """
        sec = self._require_stock(symbol)
        price = sec.get("current_price", 100)
        rating = sec.get("analyst_rating", "hold")
        target_mult = {"buy": 1.15, "hold": 1.02, "sell": 0.85}.get(rating, 1.0)
        return {
            "symbol": symbol.upper(),
            "analyst_rating": rating,
            "target_price": round(price * target_mult, 2),
            "sector": sec.get("sector", ""),
        }

    def screen_funds(
        self,
        min_expense_ratio: Optional[float] = None,
        max_expense_ratio: Optional[float] = None,
        sector: Optional[str] = None,
        min_dividend_yield: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Screen mutual funds and ETFs by criteria.

        Args:
            min_expense_ratio (float, optional): Minimum expense ratio.
            max_expense_ratio (float, optional): Maximum expense ratio.
            sector (str, optional): Filter by sector.
            min_dividend_yield (float, optional): Minimum dividend yield.

        Returns:
            List[Dict[str, Any]]: Matching funds with key metrics.
        """
        results = []
        for s in self.portfolio.values():
            if s.get("type") not in ("etf", "mutual_fund"):
                continue
            er = s.get("expense_ratio", 0)
            dy = s.get("dividend_yield", 0)
            if min_expense_ratio is not None and er < min_expense_ratio:
                continue
            if max_expense_ratio is not None and er > max_expense_ratio:
                continue
            if sector and s.get("sector", "").lower() != sector.lower():
                continue
            if min_dividend_yield is not None and dy < min_dividend_yield:
                continue
            results.append(deepcopy(s))
        return results

    # -----------------------------------------------------------------------
    # Positions
    # -----------------------------------------------------------------------

    def get_positions(self) -> Dict[str, Any]:
        """
        Get all holdings for the current profile.

        Returns:
            Dict[str, Any]: positions (Dict[symbol, {symbol, quantity,
                average_cost, current_value, unrealized_gain_loss}]),
                total_value (float).
        """
        enriched = {}
        total = 0.0
        for sym, pos in self.positions.items():
            sec = self.portfolio.get(sym, {})
            price = sec.get("current_price", 0)
            qty = pos.get("quantity", 0)
            val = round(qty * price, 2)
            gain = round(val - (qty * pos.get("average_cost", 0)), 2)
            enriched[sym] = {
                "symbol": sym,
                "quantity": qty,
                "average_cost": pos.get("average_cost", 0),
                "current_value": val,
                "unrealized_gain_loss": gain,
            }
            total += val
        return {"positions": enriched, "total_value": round(total, 2)}

    # -----------------------------------------------------------------------
    # Orders
    # -----------------------------------------------------------------------

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Place a trade order.

        Args:
            symbol (str): Security ticker symbol.
            side (str): "buy" or "sell".
            quantity (float): Number of shares.
            order_type (str): "market", "limit", or "stop".
            limit_price (float, optional): Required for limit orders.
            stop_price (float, optional): Required for stop orders.

        Returns:
            Dict[str, Any]: order_id, symbol, side, quantity, order_type,
                status, filled_price, commission.
        """
        sec = self._require_stock(symbol)
        sym = symbol.upper()

        if side not in ("buy", "sell"):
            raise FidelityError("INVALID_SIDE", "Side must be 'buy' or 'sell'.")
        valid_types = ("market", "limit", "stop")
        if order_type not in valid_types:
            raise FidelityError("INVALID_ORDER_TYPE", f"Invalid order type '{order_type}'.")
        if quantity <= 0:
            raise FidelityError("INVALID_QUANTITY", "Quantity must be positive.")

        # Commission: free for stocks/ETFs, $49.95 for non-NTF mutual funds
        commission = 0.0
        if sec.get("type") == "mutual_fund":
            commission = 49.95

        price = sec.get("current_price", 0)
        now = _utc_now_iso()

        if order_type == "market":
            filled_price = price
            status = "filled"
            if side == "buy":
                cost = quantity * filled_price + commission
                bp = self.profile.get("buying_power", 0)
                if cost > bp:
                    raise FidelityError(
                        "INSUFFICIENT_BUYING_POWER",
                        "Not enough buying power.",
                        context={"cost": cost, "buying_power": bp},
                    )
                self.profile["buying_power"] -= cost
                self.profile["cash_balance"] -= cost
                pos = self.positions.setdefault(sym, {"symbol": sym, "quantity": 0, "average_cost": 0})
                old_q = pos["quantity"]
                new_q = old_q + quantity
                pos["average_cost"] = round(
                    ((pos["average_cost"] * old_q) + (filled_price * quantity)) / new_q, 4
                ) if new_q else 0
                pos["quantity"] = new_q
            else:
                pos = self.positions.get(sym, {})
                if pos.get("quantity", 0) < quantity:
                    raise FidelityError(
                        "INSUFFICIENT_SHARES",
                        f"Only own {pos.get('quantity', 0)} shares.",
                    )
                proceeds = quantity * filled_price - commission
                self.profile["buying_power"] += proceeds
                self.profile["cash_balance"] += proceeds
                pos["quantity"] -= quantity
                if pos["quantity"] <= 0:
                    self.positions.pop(sym, None)
        else:
            filled_price = None
            status = "pending"

        order_id = self._new_id("order")
        self.orders[order_id] = {
            "order_id": order_id,
            "symbol": sym,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "limit_price": limit_price,
            "stop_price": stop_price,
            "status": status,
            "filled_price": filled_price,
            "filled_at": now if status == "filled" else None,
            "placed_at": now,
            "commission": commission,
        }
        return {
            "order_id": order_id, "symbol": sym, "side": side, "quantity": quantity,
            "order_type": order_type, "status": status, "filled_price": filled_price,
            "commission": commission,
        }

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a pending order.

        Args:
            order_id (str): The order to cancel.

        Returns:
            Dict[str, Any]: order_id (str), status (str "canceled").
        """
        order = self._require_order(order_id)
        if order.get("status") != "pending":
            raise FidelityError(
                "CANNOT_CANCEL",
                f"Cannot cancel order with status '{order.get('status')}'.",
            )
        order["status"] = "canceled"
        return {"order_id": order_id, "status": "canceled"}

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get order details.

        Args:
            order_id (str): The order identifier.

        Returns:
            Dict[str, Any]: Full order record.
        """
        order = self._require_order(order_id)
        return deepcopy(order)

    def list_orders(
        self, status: Optional[str] = None, limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List orders, optionally filtered by status.

        Args:
            status (str, optional): Filter by status.
            limit (int): Max results.

        Returns:
            List[Dict[str, Any]]: Orders sorted newest first.
        """
        results = []
        for o in self.orders.values():
            if status and o.get("status") != status:
                continue
            results.append(deepcopy(o))
        results.sort(key=lambda x: x.get("placed_at", ""), reverse=True)
        return results[:limit]

    # -----------------------------------------------------------------------
    # Watchlist
    # -----------------------------------------------------------------------

    def add_to_watchlist(self, symbol: str) -> Dict[str, Any]:
        """
        Add a security to the watchlist.

        Args:
            symbol (str): Ticker symbol to add.

        Returns:
            Dict[str, Any]: symbol (str), status (str "added").
        """
        self._require_stock(symbol)
        sym = symbol.upper()
        if sym in self.watchlist:
            raise FidelityError("ALREADY_IN_WATCHLIST", f"'{sym}' is already in the watchlist.")
        self.watchlist.append(sym)
        return {"symbol": sym, "status": "added"}

    def remove_from_watchlist(self, symbol: str) -> Dict[str, Any]:
        """
        Remove a security from the watchlist.

        Args:
            symbol (str): Ticker symbol to remove.

        Returns:
            Dict[str, Any]: symbol (str), status (str "removed").
        """
        sym = symbol.upper()
        if sym not in self.watchlist:
            raise FidelityError("NOT_IN_WATCHLIST", f"'{sym}' is not in the watchlist.")
        self.watchlist.remove(sym)
        return {"symbol": sym, "status": "removed"}

    def get_watchlist(self) -> List[Dict[str, Any]]:
        """
        Get the watchlist with current prices.

        Returns:
            List[Dict[str, Any]]: List of dicts with symbol, name,
                current_price, day_change, day_change_percent.
        """
        items = []
        for sym in self.watchlist:
            sec = self.portfolio.get(sym, {})
            items.append({
                "symbol": sym,
                "name": sec.get("name"),
                "current_price": sec.get("current_price", 0),
                "day_change": sec.get("day_change", 0),
                "day_change_percent": sec.get("day_change_percent", 0),
            })
        return items

    # -----------------------------------------------------------------------
    # Deposits & withdrawals
    # -----------------------------------------------------------------------

    def deposit_funds(
        self, amount: float, method: str = "ach",
    ) -> Dict[str, Any]:
        """
        Deposit funds into the account.

        Args:
            amount (float): Amount to deposit.
            method (str): "ach" or "wire". Defaults to "ach".

        Returns:
            Dict[str, Any]: amount, method, status, estimated_available.
        """
        if amount <= 0:
            raise FidelityError("INVALID_AMOUNT", "Amount must be positive.")
        days = 1 if method == "wire" else 3
        self.profile["cash_balance"] += amount
        self.profile["buying_power"] += amount
        arrival = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        return {"amount": amount, "method": method, "status": "processing", "estimated_available": arrival}

    def withdraw_funds(
        self, amount: float, method: str = "ach",
    ) -> Dict[str, Any]:
        """
        Withdraw funds from the account.

        Args:
            amount (float): Amount to withdraw.
            method (str): "ach" or "wire".

        Returns:
            Dict[str, Any]: amount, method, status.
        """
        if amount <= 0:
            raise FidelityError("INVALID_AMOUNT", "Amount must be positive.")
        if self.profile.get("cash_balance", 0) < amount:
            raise FidelityError("INSUFFICIENT_FUNDS", "Not enough funds.")
        self.profile["cash_balance"] -= amount
        self.profile["buying_power"] -= amount
        return {"amount": amount, "method": method, "status": "processing"}

    # -----------------------------------------------------------------------
    # Tax lots
    # -----------------------------------------------------------------------

    def get_tax_lots(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Get tax lot information for a position.

        Args:
            symbol (str): The security symbol.

        Returns:
            List[Dict[str, Any]]: Tax lots with lot_id, symbol, shares,
                cost_basis, acquired_date, current_price, gain_loss.
        """
        sym = symbol.upper()
        sec = self.portfolio.get(sym, {})
        price = sec.get("current_price", 0)
        results = []
        for lot in self.tax_lots.values():
            if lot.get("symbol") == sym:
                lot_copy = deepcopy(lot)
                lot_copy["current_price"] = price
                lot_copy["gain_loss"] = round(
                    (price - lot.get("cost_basis", 0)) * lot.get("shares", 0), 2
                )
                results.append(lot_copy)
        results.sort(key=lambda x: x.get("acquired_date", ""))
        return results
