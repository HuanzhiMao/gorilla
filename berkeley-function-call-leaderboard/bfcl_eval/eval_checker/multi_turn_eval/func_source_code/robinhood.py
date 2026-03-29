"""
Robinhood Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Commission-free trading, fractional shares, crypto, simple order types,
  recurring investments, and instant deposits.
- Single-profile, current-user perspective (no multi-user support).
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base_service import BaseServiceAPI


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class RobinhoodError(Exception):
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


# ---------------------------------------------------------------------------
# Robinhood API
# ---------------------------------------------------------------------------


DEFAULT_STATE = {
    "random_seed": 6001,
    "profile": {},
    "portfolio": {},
    "positions": {},
    "orders": {},
    "watchlist": {},
    "recurring_investments": {},
    "dividends": {},
}


class RobinhoodAPI(BaseServiceAPI):
    """
    In-memory dummy implementation of a Robinhood-like commission-free trading
    platform.  Supports stock/ETF trading, fractional shares, crypto trading,
    watchlists, recurring investments, and instant deposits.

    State variables:
    - profile: single dict with name, email, account_type, buying_power, cash_balance
    - portfolio: dict keyed by symbol -> {symbol, name, type, current_price, day_change,
      day_change_percent, bid, ask, tradable, market_open}
    - positions: dict keyed by symbol -> {symbol, quantity, average_cost}
    - orders: dict keyed by order_id -> order dict
    - watchlist: list of symbol strings
    - recurring_investments: dict keyed by investment_id
    - dividends: dict keyed by dividend_id
    """

    _STATE_KEYS = (
        "profile", "portfolio", "positions", "orders", "watchlist",
        "recurring_investments", "dividends",
    )
    _ID_COUNTER_DEFAULTS = {
        "order": 0,
        "recurring": 0,
        "dividend": 0,
    }
    _DEFAULT_SEED = 6001

    def __init__(self):
        super().__init__()
        self.profile: Dict[str, Any]
        self.portfolio: Dict[str, Dict[str, Any]]
        self.positions: Dict[str, Dict[str, Any]]
        self.orders: Dict[str, Dict[str, Any]]
        self.watchlist: List[str]
        self.recurring_investments: Dict[str, Dict[str, Any]]
        self.dividends: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Robinhood trading API, which provides "
            "commission-free stock and crypto trading, fractional shares, "
            "watchlists, recurring investments, and portfolio management."
        )


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
        self.recurring_investments = scenario.get("recurring_investments", DEFAULT_STATE_COPY["recurring_investments"])
        self.dividends = scenario.get("dividends", DEFAULT_STATE_COPY["dividends"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, RobinhoodAPI):
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
        """Look up a symbol in the portfolio (market data) dict.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: The portfolio entry for the symbol.

        Raises:
            RobinhoodError: If the symbol is not found in portfolio.
        """
        stock = self.portfolio.get(symbol.upper())
        if not stock:
            raise RobinhoodError(
                "STOCK_NOT_FOUND", f"Stock '{symbol}' not found.",
                suggested_action="Use search_stocks() to find valid symbols.",
                context={"symbol": symbol},
            )
        return stock

    def _require_order(self, order_id: str) -> Dict[str, Any]:
        """Look up an order by ID.

        Args:
            order_id (str): The order identifier.

        Returns:
            Dict[str, Any]: The order dict.

        Raises:
            RobinhoodError: If the order is not found.
        """
        order = self.orders.get(order_id)
        if not order:
            raise RobinhoodError(
                "ORDER_NOT_FOUND", f"Order '{order_id}' not found.",
                suggested_action="Use list_orders() to find valid order IDs.",
                context={"order_id": order_id},
            )
        return order

    # -----------------------------------------------------------------------
    # Account
    # -----------------------------------------------------------------------

    def get_account(self) -> Dict[str, Any]:
        """
        Get the current user's Robinhood account summary.

        Returns:
            Dict[str, Any]: Account profile with fields:
                name (str), email (str), account_type (str),
                buying_power (float), cash_balance (float).
        """
        return deepcopy(self.profile)

    # -----------------------------------------------------------------------
    # Stock quotes & search
    # -----------------------------------------------------------------------

    def get_stock_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get a real-time quote for a stock or asset.

        Args:
            symbol (str): The ticker symbol (e.g. "AAPL").

        Returns:
            Dict[str, Any]: Quote with fields:
                symbol (str), name (str), type (str),
                current_price (float), day_change (float),
                day_change_percent (float), and optional bid, ask,
                tradable, market_open.
        """
        stock = self._require_stock(symbol)
        return deepcopy(stock)

    def search_stocks(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search for stocks/assets by name or symbol.

        Args:
            query (str): Search string matched against name and symbol.
            limit (int): Maximum results. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Matching entries from portfolio with all fields.
        """
        results = []
        for s in self.portfolio.values():
            if _matches_query(s.get("name", ""), query) or _matches_query(s.get("symbol", ""), query):
                results.append(deepcopy(s))
        return results[:limit]

    # -----------------------------------------------------------------------
    # Portfolio
    # -----------------------------------------------------------------------

    def get_portfolio(self) -> Dict[str, Any]:
        """
        Get the current user's holdings (positions enriched with market data).

        Returns:
            Dict[str, Any]: Portfolio with fields:
                holdings (Dict[symbol, {symbol, quantity, average_cost,
                current_value, unrealized_gain_loss}]), total_value (float).
        """
        enriched = {}
        total = 0.0
        for sym, pos in self.positions.items():
            stock = self.portfolio.get(sym, {})
            price = stock.get("current_price", 0)
            quantity = pos.get("quantity", 0)
            current_value = round(quantity * price, 2)
            avg_cost = pos.get("average_cost", 0)
            unrealized = round(current_value - (quantity * avg_cost), 2)
            enriched[sym] = {
                "symbol": sym,
                "quantity": quantity,
                "average_cost": avg_cost,
                "current_value": current_value,
                "unrealized_gain_loss": unrealized,
            }
            total += current_value
        return {
            "holdings": enriched,
            "total_value": round(total, 2),
        }

    def get_portfolio_history(
        self, span: str = "week",
    ) -> Dict[str, Any]:
        """
        Get portfolio value over time (simulated).

        Args:
            span (str): Time span — "day", "week", "month", "3month",
                "year", "all". Defaults to "week".

        Returns:
            Dict[str, Any]:
                span (str), data_points (List[Dict]) each with
                timestamp (str) and value (float).
        """
        portfolio = self.get_portfolio()
        current = portfolio.get("total_value", 0)
        span_days = {"day": 1, "week": 7, "month": 30, "3month": 90, "year": 365, "all": 730}
        days = span_days.get(span, 7)
        points = []
        for i in range(days, -1, -1):
            jitter = self._rng.uniform(-0.03, 0.03)
            val = round(current * (1 + jitter * (i / max(days, 1))), 2)
            dt = datetime.now(timezone.utc) - timedelta(days=i)
            points.append({"timestamp": dt.isoformat(), "value": val})
        return {"span": span, "data_points": points}

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
        time_in_force: str = "gfd",
    ) -> Dict[str, Any]:
        """
        Place a stock order.

        Args:
            symbol (str): Stock ticker symbol.
            side (str): "buy" or "sell".
            quantity (float): Number of shares (supports fractional).
            order_type (str): "market", "limit", or "stop".
            limit_price (float, optional): Required for limit orders.
            stop_price (float, optional): Required for stop orders.
            time_in_force (str): "gfd" (good for day) or "gtc" (good till canceled).
                Used for validation only; not stored in the order.

        Returns:
            Dict[str, Any]:
                order_id (str), symbol (str), side (str), quantity (float),
                order_type (str), status (str), filled_price (float | None).
        """
        stock = self._require_stock(symbol)
        sym = symbol.upper()

        if side not in ("buy", "sell"):
            raise RobinhoodError("INVALID_SIDE", "Side must be 'buy' or 'sell'.")
        if order_type not in ("market", "limit", "stop"):
            raise RobinhoodError("INVALID_ORDER_TYPE", f"Invalid order type '{order_type}'.")
        if quantity <= 0:
            raise RobinhoodError("INVALID_QUANTITY", "Quantity must be greater than zero.")
        if order_type == "limit" and limit_price is None:
            raise RobinhoodError("LIMIT_PRICE_REQUIRED", "limit_price is required for limit orders.")
        if order_type == "stop" and stop_price is None:
            raise RobinhoodError("STOP_PRICE_REQUIRED", "stop_price is required for stop orders.")
        if time_in_force not in ("gfd", "gtc"):
            raise RobinhoodError("INVALID_TIF", "time_in_force must be 'gfd' or 'gtc'.")

        price = stock.get("current_price", 0)
        now = _utc_now_iso()

        if side == "buy":
            cost = quantity * price
            if cost > self.profile.get("buying_power", 0):
                raise RobinhoodError(
                    "INSUFFICIENT_BUYING_POWER",
                    f"Need ${cost:.2f} but only have ${self.profile.get('buying_power', 0):.2f}.",
                    context={"cost": cost, "buying_power": self.profile.get("buying_power", 0)},
                )
        else:
            pos = self.positions.get(sym, {})
            if pos.get("quantity", 0) < quantity:
                raise RobinhoodError(
                    "INSUFFICIENT_SHARES",
                    f"You only own {pos.get('quantity', 0)} shares of {sym}.",
                    context={"owned": pos.get("quantity", 0), "requested": quantity},
                )

        # Simulate fill for market orders
        if order_type == "market":
            filled_price = price
            status = "filled"
            if side == "buy":
                self.profile["buying_power"] = self.profile.get("buying_power", 0) - quantity * filled_price
                self.profile["cash_balance"] = self.profile.get("cash_balance", 0) - quantity * filled_price
                pos = self.positions.setdefault(sym, {"symbol": sym, "quantity": 0, "average_cost": 0})
                old_qty = pos["quantity"]
                old_cost = pos["average_cost"]
                new_qty = old_qty + quantity
                pos["average_cost"] = round(((old_cost * old_qty) + (filled_price * quantity)) / new_qty, 4) if new_qty else 0
                pos["quantity"] = new_qty
            else:
                proceeds = quantity * filled_price
                self.profile["buying_power"] = self.profile.get("buying_power", 0) + proceeds
                self.profile["cash_balance"] = self.profile.get("cash_balance", 0) + proceeds
                pos = self.positions.get(sym, {})
                pos["quantity"] = pos.get("quantity", 0) - quantity
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
        }

        return {
            "order_id": order_id,
            "symbol": sym,
            "side": side,
            "quantity": quantity,
            "order_type": order_type,
            "status": status,
            "filled_price": filled_price,
        }

    def place_fractional_order(
        self,
        symbol: str,
        amount_in_dollars: float,
        side: str,
    ) -> Dict[str, Any]:
        """
        Buy or sell a dollar amount of a stock (fractional shares).

        Args:
            symbol (str): Stock ticker symbol.
            amount_in_dollars (float): Dollar amount to buy/sell.
            side (str): "buy" or "sell".

        Returns:
            Dict[str, Any]: Order result (same as place_order).
        """
        stock = self._require_stock(symbol)
        price = stock.get("current_price", 1)
        quantity = round(amount_in_dollars / price, 6)
        return self.place_order(symbol, side, quantity, order_type="market")

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """
        Cancel a pending order.

        Args:
            order_id (str): The order to cancel.

        Returns:
            Dict[str, Any]:
                order_id (str), status (str "canceled").
        """
        order = self._require_order(order_id)
        if order.get("status") != "pending":
            raise RobinhoodError("CANNOT_CANCEL", f"Cannot cancel order with status '{order.get('status')}'.")
        order["status"] = "canceled"
        return {"order_id": order_id, "status": "canceled"}

    def get_order(self, order_id: str) -> Dict[str, Any]:
        """
        Get details of a specific order.

        Args:
            order_id (str): The order identifier.

        Returns:
            Dict[str, Any]: Full order object.
        """
        order = self._require_order(order_id)
        return deepcopy(order)

    def list_orders(
        self, status: Optional[str] = None, limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List orders, optionally filtered by status.

        Args:
            status (str, optional): Filter by status
                (pending/partially_filled/filled/canceled/failed).
            limit (int): Max results. Defaults to 20.

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
        Add a stock to the watchlist.

        Args:
            symbol (str): Stock ticker to add.

        Returns:
            Dict[str, Any]: symbol (str), status (str "added"), watchlist_size (int).
        """
        self._require_stock(symbol)
        sym = symbol.upper()
        if sym in self.watchlist:
            raise RobinhoodError("ALREADY_IN_WATCHLIST", f"'{sym}' is already in your watchlist.")
        self.watchlist.append(sym)
        return {"symbol": sym, "status": "added", "watchlist_size": len(self.watchlist)}

    def remove_from_watchlist(self, symbol: str) -> Dict[str, Any]:
        """
        Remove a stock from the watchlist.

        Args:
            symbol (str): Stock ticker to remove.

        Returns:
            Dict[str, Any]: symbol (str), status (str "removed").
        """
        sym = symbol.upper()
        if sym not in self.watchlist:
            raise RobinhoodError("NOT_IN_WATCHLIST", f"'{sym}' is not in your watchlist.")
        self.watchlist.remove(sym)
        return {"symbol": sym, "status": "removed"}

    def get_watchlist(self) -> List[Dict[str, Any]]:
        """
        Get the watchlist with current prices.

        Returns:
            List[Dict[str, Any]]: Entries with symbol, name, current_price,
                day_change, day_change_percent.
        """
        results = []
        for sym in self.watchlist:
            market = self.portfolio.get(sym, {})
            results.append({
                "symbol": sym,
                "name": market.get("name"),
                "current_price": market.get("current_price", 0),
                "day_change": market.get("day_change", 0),
                "day_change_percent": market.get("day_change_percent", 0),
            })
        return results

    # -----------------------------------------------------------------------
    # Crypto
    # -----------------------------------------------------------------------

    def get_crypto_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get a crypto asset quote.

        Args:
            symbol (str): Crypto symbol (e.g. "BTC", "ETH").

        Returns:
            Dict[str, Any]: The portfolio entry for the crypto asset, including
                symbol, name, type, current_price, day_change, day_change_percent.
        """
        sym = symbol.upper()
        entry = self.portfolio.get(sym)
        if not entry:
            raise RobinhoodError("CRYPTO_NOT_FOUND", f"Crypto '{sym}' not found.",
                                 suggested_action="Check available crypto assets.")
        return deepcopy(entry)

    def buy_crypto(self, symbol: str, amount_in_dollars: float) -> Dict[str, Any]:
        """
        Buy cryptocurrency with a dollar amount.

        Args:
            symbol (str): Crypto symbol (e.g. "BTC").
            amount_in_dollars (float): Dollar amount to spend.

        Returns:
            Dict[str, Any]: symbol (str), quantity (float), amount (float),
                status (str "filled").
        """
        sym = symbol.upper()
        entry = self.portfolio.get(sym)
        if not entry:
            raise RobinhoodError("CRYPTO_NOT_FOUND", f"Crypto '{sym}' not found.")
        if amount_in_dollars <= 0:
            raise RobinhoodError("INVALID_AMOUNT", "Amount must be positive.")
        if amount_in_dollars > self.profile.get("buying_power", 0):
            raise RobinhoodError("INSUFFICIENT_BUYING_POWER", "Not enough buying power.")

        price = entry.get("current_price", 1)
        quantity = round(amount_in_dollars / price, 8)
        self.profile["buying_power"] = self.profile.get("buying_power", 0) - amount_in_dollars
        self.profile["cash_balance"] = self.profile.get("cash_balance", 0) - amount_in_dollars

        pos = self.positions.setdefault(sym, {"symbol": sym, "quantity": 0, "average_cost": 0})
        old_q = pos["quantity"]
        old_c = pos["average_cost"]
        new_q = old_q + quantity
        pos["average_cost"] = round(((old_c * old_q) + (price * quantity)) / new_q, 4) if new_q else 0
        pos["quantity"] = new_q

        return {"symbol": sym, "quantity": quantity, "amount": amount_in_dollars, "status": "filled"}

    def sell_crypto(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """
        Sell a quantity of cryptocurrency.

        Args:
            symbol (str): Crypto symbol.
            quantity (float): Amount of crypto to sell.

        Returns:
            Dict[str, Any]: symbol (str), quantity (float), proceeds (float),
                status (str "filled").
        """
        sym = symbol.upper()
        entry = self.portfolio.get(sym)
        if not entry:
            raise RobinhoodError("CRYPTO_NOT_FOUND", f"Crypto '{sym}' not found.")
        pos = self.positions.get(sym, {})
        if pos.get("quantity", 0) < quantity:
            raise RobinhoodError("INSUFFICIENT_CRYPTO", f"You only own {pos.get('quantity', 0)} {sym}.")

        price = entry.get("current_price", 0)
        proceeds = round(quantity * price, 2)
        pos["quantity"] = pos.get("quantity", 0) - quantity
        if pos["quantity"] <= 0:
            self.positions.pop(sym, None)
        self.profile["buying_power"] = self.profile.get("buying_power", 0) + proceeds
        self.profile["cash_balance"] = self.profile.get("cash_balance", 0) + proceeds

        return {"symbol": sym, "quantity": quantity, "proceeds": proceeds, "status": "filled"}

    def get_crypto_portfolio(self) -> Dict[str, Any]:
        """
        Get the current user's crypto holdings (positions where the portfolio
        entry has type="crypto").

        Returns:
            Dict[str, Any]: holdings (Dict[symbol, {quantity, average_cost,
                current_value}]), total_value (float).
        """
        enriched = {}
        total = 0.0
        for sym, pos in self.positions.items():
            c = self.portfolio.get(sym, {})
            if c.get("type") != "crypto":
                continue
            price = c.get("current_price", 0)
            val = round(pos.get("quantity", 0) * price, 2)
            enriched[sym] = {
                "quantity": pos.get("quantity", 0),
                "average_cost": pos.get("average_cost", 0),
                "current_value": val,
            }
            total += val
        return {"holdings": enriched, "total_value": round(total, 2)}

    # -----------------------------------------------------------------------
    # Recurring investments
    # -----------------------------------------------------------------------

    def setup_recurring_investment(
        self, symbol: str, amount: float, frequency: str,
    ) -> Dict[str, Any]:
        """
        Set up automatic recurring investment in a stock.

        Args:
            symbol (str): Stock ticker.
            amount (float): Dollar amount per investment.
            frequency (str): "daily", "weekly", "biweekly", or "monthly".

        Returns:
            Dict[str, Any]: investment_id (str), symbol (str), amount (float),
                frequency (str), next_execution (str), status (str "active").
        """
        self._require_stock(symbol)
        if amount <= 0:
            raise RobinhoodError("INVALID_AMOUNT", "Amount must be positive.")
        if frequency not in ("daily", "weekly", "biweekly", "monthly"):
            raise RobinhoodError("INVALID_FREQUENCY", f"Invalid frequency '{frequency}'.")

        freq_days = {"daily": 1, "weekly": 7, "biweekly": 14, "monthly": 30}
        next_exec = datetime.now(timezone.utc) + timedelta(days=freq_days[frequency])

        inv_id = self._new_id("recurring")
        self.recurring_investments[inv_id] = {
            "investment_id": inv_id,
            "symbol": symbol.upper(),
            "amount": amount,
            "frequency": frequency,
            "next_execution": next_exec.isoformat(),
            "status": "active",
        }
        return {
            "investment_id": inv_id,
            "symbol": symbol.upper(),
            "amount": amount,
            "frequency": frequency,
            "next_execution": next_exec.isoformat(),
            "status": "active",
        }

    def cancel_recurring_investment(self, investment_id: str) -> Dict[str, Any]:
        """
        Cancel a recurring investment.

        Args:
            investment_id (str): The recurring investment to cancel.

        Returns:
            Dict[str, Any]: investment_id (str), status (str "canceled").
        """
        inv = self.recurring_investments.get(investment_id)
        if not inv:
            raise RobinhoodError("INVESTMENT_NOT_FOUND", f"Recurring investment '{investment_id}' not found.")
        inv["status"] = "canceled"
        return {"investment_id": investment_id, "status": "canceled"}

    # -----------------------------------------------------------------------
    # Dividends
    # -----------------------------------------------------------------------

    def get_dividends(self) -> List[Dict[str, Any]]:
        """
        Get dividend history.

        Returns:
            List[Dict[str, Any]]: All dividend records with dividend_id, symbol,
                amount, ex_date, pay_date, status.
        """
        results = []
        for d in self.dividends.values():
            results.append(deepcopy(d))
        results.sort(key=lambda x: x.get("pay_date", ""), reverse=True)
        return results

    # -----------------------------------------------------------------------
    # Deposits & withdrawals
    # -----------------------------------------------------------------------

    def deposit_funds(self, amount: float) -> Dict[str, Any]:
        """
        Deposit funds into the Robinhood account.  Instant deposits are
        available up to the user's instant deposit limit.

        Args:
            amount (float): Amount to deposit.

        Returns:
            Dict[str, Any]: amount (float), instant_available (float),
                pending (float), status (str).
        """
        if amount <= 0:
            raise RobinhoodError("INVALID_AMOUNT", "Amount must be positive.")

        instant_limit = self.profile.get("instant_deposit_limit", 1000.0)
        instant = min(amount, instant_limit)
        pending = amount - instant

        self.profile["buying_power"] = self.profile.get("buying_power", 0) + instant
        self.profile["cash_balance"] = self.profile.get("cash_balance", 0) + instant

        return {
            "amount": amount,
            "instant_available": instant,
            "pending": pending,
            "status": "completed" if pending == 0 else "partially_instant",
        }

    def withdraw_funds(self, amount: float) -> Dict[str, Any]:
        """
        Withdraw funds to linked bank account.

        Args:
            amount (float): Amount to withdraw.

        Returns:
            Dict[str, Any]: amount (float), status (str "processing"),
                estimated_arrival (str).
        """
        if amount <= 0:
            raise RobinhoodError("INVALID_AMOUNT", "Amount must be positive.")
        if amount > self.profile.get("cash_balance", 0):
            raise RobinhoodError("INSUFFICIENT_FUNDS", "Not enough cash to withdraw.")

        self.profile["buying_power"] = self.profile.get("buying_power", 0) - amount
        self.profile["cash_balance"] = self.profile.get("cash_balance", 0) - amount
        arrival = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        return {"amount": amount, "status": "processing", "estimated_arrival": arrival}
