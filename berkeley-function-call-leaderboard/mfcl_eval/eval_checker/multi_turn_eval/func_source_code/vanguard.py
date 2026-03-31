"""
Vanguard Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Low-cost index fund specialist: target-date funds, auto-invest, DRIP,
  and retirement-focused contributions.
- Single-profile (current-user) perspective; no multi-user/multi-account state.
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


class VanguardError(Exception):
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
# Vanguard API
# ---------------------------------------------------------------------------


DEFAULT_STATE = {
    "random_seed": 6003,
    "profile": {},
    "portfolio": {},
    "positions": {},
    "orders": {},
    "watchlist": {},
    "auto_investments": {},
    "dividends": {},
    "contributions": {},
}


class VanguardAPI(PatchableMixin):
    """
    In-memory dummy implementation of a Vanguard-like low-cost index fund
    investment platform.

    Specializes in index funds/ETFs, target-date retirement funds, automatic
    investing, dividend reinvestment (DRIP), and contribution tracking.

    Single-profile perspective — no multi-user/multi-account state.
    """


    def __init__(self):
        self._id_counters = { "order": 0, "auto_invest": 0, "dividend": 0, "contribution": 0, }
        self.profile: Dict[str, Any]
        self.portfolio: Dict[str, Dict[str, Any]]
        self.positions: Dict[str, Dict[str, Any]]
        self.orders: Dict[str, Dict[str, Any]]
        self.watchlist: List[str]
        self.auto_investments: Dict[str, Dict[str, Any]]
        self.dividends: Dict[str, Dict[str, Any]]
        self.contributions: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Vanguard investment API, which provides "
            "low-cost index fund and ETF investing, target-date retirement funds, "
            "automatic investing, dividend reinvestment, and contribution tracking."
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
        self.auto_investments = scenario.get("auto_investments", DEFAULT_STATE_COPY["auto_investments"])
        self.dividends = scenario.get("dividends", DEFAULT_STATE_COPY["dividends"])
        self.contributions = scenario.get("contributions", DEFAULT_STATE_COPY["contributions"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, VanguardAPI):
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

    def _require_stock(self, fund_id: str) -> Dict[str, Any]:
        """Look up a fund/security in the portfolio catalog."""
        entry = self.portfolio.get(fund_id)
        if not entry:
            raise VanguardError("FUND_NOT_FOUND", f"Fund '{fund_id}' not found.",
                                suggested_action="Use search_stocks() to find valid fund IDs.")
        return entry

    def _require_order(self, order_id: str) -> Dict[str, Any]:
        order = self.orders.get(order_id)
        if not order:
            raise VanguardError("ORDER_NOT_FOUND", f"Order '{order_id}' not found.")
        return order

    # -----------------------------------------------------------------------
    # Profile
    # -----------------------------------------------------------------------

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get the current user's profile.

        Returns:
            Dict[str, Any]: name, email, account_type, buying_power,
                cash_balance.
        """
        return deepcopy(self.profile)

    # -----------------------------------------------------------------------
    # Funds / portfolio catalog
    # -----------------------------------------------------------------------

    def get_stock_quote(self, fund_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a fund.

        Args:
            fund_id (str): The fund identifier.

        Returns:
            Dict[str, Any]: Full portfolio entry including symbol, name,
                type, current_price, day_change, day_change_percent, and
                fund-specific fields (expense_ratio, minimum_investment,
                share_class, category, dividend_yield, returns, etc.).
        """
        return deepcopy(self._require_stock(fund_id))

    def search_stocks(
        self, query: str, category: Optional[str] = None,
        share_class: Optional[str] = None, limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for funds by name, symbol, or category.

        Args:
            query (str): Search text.
            category (str, optional): Filter — "us_stock", "international",
                "bond", "balanced", "target_date".
            share_class (str, optional): "investor", "admiral", or "etf".
            limit (int): Max results.

        Returns:
            List[Dict[str, Any]]: Matching funds from the portfolio catalog.
        """
        results = []
        for f in self.portfolio.values():
            if category and f.get("category") != category:
                continue
            if share_class and f.get("share_class") != share_class:
                continue
            if _matches_query(f.get("name", ""), query) or _matches_query(f.get("symbol", ""), query):
                results.append(deepcopy(f))
        return results[:limit]

    def compare_funds(self, fund_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Compare multiple funds side by side.

        Args:
            fund_ids (List[str]): Fund IDs to compare (2-5).

        Returns:
            List[Dict[str, Any]]: Fund details for comparison.
        """
        if len(fund_ids) < 2:
            raise VanguardError("TOO_FEW_FUNDS", "At least 2 funds required for comparison.")
        if len(fund_ids) > 5:
            raise VanguardError("TOO_MANY_FUNDS", "Maximum 5 funds for comparison.")
        results = []
        for fid in fund_ids:
            fund = self._require_stock(fid)
            results.append(deepcopy(fund))
        return results

    def get_target_date_fund(self, retirement_year: int) -> Dict[str, Any]:
        """
        Find the target-date fund closest to a retirement year.

        Args:
            retirement_year (int): The target retirement year.

        Returns:
            Dict[str, Any]: The matching target-date fund.
        """
        best = None
        best_diff = float("inf")
        for f in self.portfolio.values():
            if f.get("type") != "target_date":
                continue
            name = f.get("name", "")
            for word in name.split():
                if word.isdigit() and len(word) == 4:
                    diff = abs(int(word) - retirement_year)
                    if diff < best_diff:
                        best_diff = diff
                        best = f
                    break
        if not best:
            raise VanguardError("NO_TARGET_DATE_FUND",
                                f"No target-date fund found near year {retirement_year}.",
                                suggested_action="Search for available target-date funds.")
        return deepcopy(best)

    # -----------------------------------------------------------------------
    # Positions (holdings)
    # -----------------------------------------------------------------------

    def get_positions(self) -> Dict[str, Any]:
        """
        Get all fund holdings.

        Returns:
            Dict[str, Any]: positions (Dict[fund_id, {symbol, quantity,
                average_cost, current_price, current_value,
                unrealized_gain_loss, dividend_reinvest}]),
                total_value (float).
        """
        enriched = {}
        total = 0.0
        for fid, pos in self.positions.items():
            fund = self.portfolio.get(fid, {})
            price = fund.get("current_price", fund.get("nav", 0))
            quantity = pos.get("quantity", 0)
            val = round(quantity * price, 2)
            gain = round(val - (quantity * pos.get("average_cost", 0)), 2)
            enriched[fid] = {
                "symbol": fid,
                "fund_name": fund.get("name", ""),
                "quantity": quantity,
                "average_cost": pos.get("average_cost", 0),
                "current_price": price,
                "current_value": val,
                "unrealized_gain_loss": gain,
                "dividend_reinvest": pos.get("dividend_reinvest", True),
            }
            total += val
        return {"positions": enriched, "total_value": round(total, 2)}

    # -----------------------------------------------------------------------
    # Trading
    # -----------------------------------------------------------------------

    def buy_fund(self, fund_id: str, amount: float) -> Dict[str, Any]:
        """
        Buy a fund with a dollar amount.  Fund purchases are executed at
        end-of-day NAV.  Some funds have minimum investment requirements.

        Args:
            fund_id (str): The fund to purchase.
            amount (float): Dollar amount to invest.

        Returns:
            Dict[str, Any]: order_id, fund_id, amount, estimated_shares,
                status, nav_price.
        """
        fund = self._require_stock(fund_id)

        if amount <= 0:
            raise VanguardError("INVALID_AMOUNT", "Amount must be positive.")

        min_invest = fund.get("minimum_investment", 0)
        existing = self.positions.get(fund_id)
        if not existing and amount < min_invest:
            raise VanguardError(
                "BELOW_MINIMUM",
                f"Minimum initial investment is ${min_invest:.2f}.",
                context={"minimum": min_invest, "amount": amount},
            )

        if amount > self.profile.get("cash_balance", 0):
            raise VanguardError("INSUFFICIENT_FUNDS", "Not enough funds.")

        price = fund.get("current_price", fund.get("nav", 100))
        shares = round(amount / price, 6)

        self.profile["cash_balance"] = self.profile.get("cash_balance", 0) - amount
        self.profile["buying_power"] = self.profile.get("buying_power", 0) - amount

        pos = self.positions.setdefault(fund_id, {
            "symbol": fund_id, "quantity": 0, "average_cost": 0, "dividend_reinvest": True,
        })
        old_s = pos["quantity"]
        new_s = old_s + shares
        pos["average_cost"] = round(((pos["average_cost"] * old_s) + (price * shares)) / new_s, 4) if new_s else 0
        pos["quantity"] = new_s

        order_id = self._new_id("order")
        now = _utc_now_iso()
        self.orders[order_id] = {
            "order_id": order_id,
            "symbol": fund_id,
            "side": "buy",
            "order_type": "market",
            "quantity": shares,
            "status": "filled",
            "filled_price": price,
            "placed_at": now,
            "amount": amount,
        }
        return {
            "order_id": order_id, "fund_id": fund_id, "amount": amount,
            "estimated_shares": shares, "status": "filled", "nav_price": price,
        }

    def sell_fund(
        self, fund_id: str,
        shares: Optional[float] = None, amount: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Sell a fund by shares or dollar amount.

        Args:
            fund_id (str): The fund to sell.
            shares (float, optional): Number of shares to sell.
            amount (float, optional): Dollar amount to sell.
                One of shares or amount must be provided.

        Returns:
            Dict[str, Any]: order_id, fund_id, shares_sold, proceeds, status.
        """
        fund = self._require_stock(fund_id)
        pos = self.positions.get(fund_id)
        if not pos or pos.get("quantity", 0) <= 0:
            raise VanguardError("NO_POSITION", f"No holdings in fund '{fund_id}'.")

        price = fund.get("current_price", fund.get("nav", 100))

        if shares is not None:
            sell_shares = shares
        elif amount is not None:
            sell_shares = round(amount / price, 6)
        else:
            raise VanguardError("NO_QUANTITY", "Provide either shares or amount.")

        if sell_shares > pos["quantity"]:
            raise VanguardError("INSUFFICIENT_SHARES", f"Only own {pos['quantity']} shares.")

        proceeds = round(sell_shares * price, 2)
        pos["quantity"] -= sell_shares
        if pos["quantity"] <= 0:
            self.positions.pop(fund_id, None)

        self.profile["cash_balance"] = self.profile.get("cash_balance", 0) + proceeds
        self.profile["buying_power"] = self.profile.get("buying_power", 0) + proceeds

        order_id = self._new_id("order")
        now = _utc_now_iso()
        self.orders[order_id] = {
            "order_id": order_id,
            "symbol": fund_id,
            "side": "sell",
            "order_type": "market",
            "quantity": sell_shares,
            "status": "filled",
            "filled_price": price,
            "placed_at": now,
            "amount": proceeds,
        }
        return {
            "order_id": order_id, "fund_id": fund_id,
            "shares_sold": sell_shares, "proceeds": proceeds, "status": "filled",
        }

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

    def list_orders(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List orders, sorted newest first.

        Args:
            limit (int): Max results.

        Returns:
            List[Dict[str, Any]]: Orders.
        """
        results = [deepcopy(o) for o in self.orders.values()]
        results.sort(key=lambda x: x.get("placed_at", ""), reverse=True)
        return results[:limit]

    # -----------------------------------------------------------------------
    # Watchlist
    # -----------------------------------------------------------------------

    def add_to_watchlist(self, symbol: str) -> Dict[str, Any]:
        """
        Add a fund to the watchlist.

        Args:
            symbol (str): Fund ID to add.

        Returns:
            Dict[str, Any]: symbol (str), status (str "added").
        """
        self._require_stock(symbol)
        if symbol in self.watchlist:
            raise VanguardError("ALREADY_IN_WATCHLIST", f"'{symbol}' is already in your watchlist.")
        self.watchlist.append(symbol)
        return {"symbol": symbol, "status": "added"}

    def remove_from_watchlist(self, symbol: str) -> Dict[str, Any]:
        """
        Remove a fund from the watchlist.

        Args:
            symbol (str): Fund ID to remove.

        Returns:
            Dict[str, Any]: symbol (str), status (str "removed").
        """
        if symbol not in self.watchlist:
            raise VanguardError("NOT_IN_WATCHLIST", f"'{symbol}' is not in your watchlist.")
        self.watchlist.remove(symbol)
        return {"symbol": symbol, "status": "removed"}

    def get_watchlist(self) -> List[Dict[str, Any]]:
        """
        Get the watchlist with current prices.

        Returns:
            List[Dict[str, Any]]: Funds with symbol, name, current_price,
                day_change, day_change_percent.
        """
        items = []
        for sym in self.watchlist:
            fund = self.portfolio.get(sym, {})
            items.append({
                "symbol": sym,
                "name": fund.get("name"),
                "current_price": fund.get("current_price", 0),
                "day_change": fund.get("day_change", 0),
                "day_change_percent": fund.get("day_change_percent", 0),
            })
        return items

    # -----------------------------------------------------------------------
    # Auto-invest
    # -----------------------------------------------------------------------

    def setup_auto_invest(
        self, fund_id: str, amount: float, frequency: str,
    ) -> Dict[str, Any]:
        """
        Set up automatic recurring investments.

        Args:
            fund_id (str): The fund to invest in.
            amount (float): Dollar amount per investment.
            frequency (str): "weekly", "biweekly", "monthly", or "quarterly".

        Returns:
            Dict[str, Any]: investment_id, fund_id, amount, frequency,
                next_execution, status.
        """
        self._require_stock(fund_id)
        if amount <= 0:
            raise VanguardError("INVALID_AMOUNT", "Amount must be positive.")
        valid_freq = ("weekly", "biweekly", "monthly", "quarterly")
        if frequency not in valid_freq:
            raise VanguardError("INVALID_FREQUENCY", f"Must be one of {valid_freq}.")

        freq_days = {"weekly": 7, "biweekly": 14, "monthly": 30, "quarterly": 90}
        next_exec = (datetime.now(timezone.utc) + timedelta(days=freq_days[frequency])).isoformat()

        inv_id = self._new_id("auto_invest")
        self.auto_investments[inv_id] = {
            "investment_id": inv_id,
            "fund_id": fund_id, "amount": amount, "frequency": frequency,
            "next_execution": next_exec, "status": "active",
        }
        return {
            "investment_id": inv_id, "fund_id": fund_id, "amount": amount,
            "frequency": frequency, "next_execution": next_exec, "status": "active",
        }

    def cancel_auto_invest(self, investment_id: str) -> Dict[str, Any]:
        """
        Cancel an automatic investment.

        Args:
            investment_id (str): The auto-investment to cancel.

        Returns:
            Dict[str, Any]: investment_id (str), status (str "canceled").
        """
        inv = self.auto_investments.get(investment_id)
        if not inv:
            raise VanguardError("INVESTMENT_NOT_FOUND", f"Auto-investment '{investment_id}' not found.")
        inv["status"] = "canceled"
        return {"investment_id": investment_id, "status": "canceled"}

    def list_auto_investments(self) -> List[Dict[str, Any]]:
        """
        List all active auto-investments.

        Returns:
            List[Dict[str, Any]]: Active auto-investment records.
        """
        return [deepcopy(i) for i in self.auto_investments.values()
                if i.get("status") == "active"]

    # -----------------------------------------------------------------------
    # Dividends
    # -----------------------------------------------------------------------

    def toggle_dividend_reinvestment(
        self, fund_id: str, reinvest: bool,
    ) -> Dict[str, Any]:
        """
        Enable or disable dividend reinvestment (DRIP) for a holding.

        Args:
            fund_id (str): The fund.
            reinvest (bool): True to reinvest dividends, False to receive cash.

        Returns:
            Dict[str, Any]: fund_id, reinvest (bool), status.
        """
        pos = self.positions.get(fund_id)
        if not pos:
            raise VanguardError("NO_POSITION", f"No holdings in fund '{fund_id}'.")
        pos["dividend_reinvest"] = reinvest
        return {"fund_id": fund_id, "reinvest": reinvest, "status": "updated"}

    def get_dividend_history(
        self, fund_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get dividend history, optionally filtered by fund.

        Args:
            fund_id (str, optional): Filter by specific fund.

        Returns:
            List[Dict[str, Any]]: Dividend records.
        """
        results = []
        for d in self.dividends.values():
            if fund_id and d.get("fund_id") != fund_id:
                continue
            results.append(deepcopy(d))
        results.sort(key=lambda x: x.get("date", ""), reverse=True)
        return results

    # -----------------------------------------------------------------------
    # Contributions & withdrawals
    # -----------------------------------------------------------------------

    def contribute(
        self, amount: float, tax_year: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Make a contribution to the account.  For IRA accounts, contributions
        are tracked against annual limits.

        Args:
            amount (float): Contribution amount.
            tax_year (int, optional): Tax year for the contribution.
                Defaults to current year.

        Returns:
            Dict[str, Any]: contribution_id, amount, tax_year, status.
        """
        if amount <= 0:
            raise VanguardError("INVALID_AMOUNT", "Amount must be positive.")

        year = tax_year or datetime.now(timezone.utc).year
        acct_type = self.profile.get("account_type", "individual")

        # Check IRA contribution limits
        if acct_type in ("roth_ira", "traditional_ira"):
            annual_limit = 7000.0  # 2024 limit
            year_total = sum(
                c.get("amount", 0) for c in self.contributions.values()
                if c.get("tax_year") == year
            )
            if year_total + amount > annual_limit:
                raise VanguardError(
                    "CONTRIBUTION_LIMIT_EXCEEDED",
                    f"IRA annual limit is ${annual_limit:.2f}. Already contributed ${year_total:.2f}.",
                    context={"limit": annual_limit, "contributed": year_total},
                )

        self.profile["cash_balance"] = self.profile.get("cash_balance", 0) + amount
        self.profile["buying_power"] = self.profile.get("buying_power", 0) + amount

        cid = self._new_id("contribution")
        self.contributions[cid] = {
            "contribution_id": cid,
            "amount": amount, "tax_year": year, "type": "regular",
            "created_at": _utc_now_iso(),
        }
        return {"contribution_id": cid, "amount": amount, "tax_year": year, "status": "completed"}

    def withdraw(self, amount: float) -> Dict[str, Any]:
        """
        Withdraw funds from the account.

        Args:
            amount (float): Amount to withdraw.

        Returns:
            Dict[str, Any]: amount, status, estimated_arrival.
        """
        if amount <= 0:
            raise VanguardError("INVALID_AMOUNT", "Amount must be positive.")
        if amount > self.profile.get("cash_balance", 0):
            raise VanguardError("INSUFFICIENT_FUNDS", "Not enough funds.")
        self.profile["cash_balance"] = self.profile.get("cash_balance", 0) - amount
        self.profile["buying_power"] = self.profile.get("buying_power", 0) - amount
        arrival = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        return {"amount": amount, "status": "processing", "estimated_arrival": arrival}
