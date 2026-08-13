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
    "target_allocation": {},
    "rmd_info": {},
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
        self._id_counters = { "order": 0, "auto_invest": 0, "dividend": 0, "contribution": 0, "rmd_schedule": 0, }
        self.profile: Dict[str, Any]
        self.portfolio: Dict[str, Dict[str, Any]]
        self.positions: Dict[str, Dict[str, Any]]
        self.orders: Dict[str, Dict[str, Any]]
        self.watchlist: List[str]
        self.auto_investments: Dict[str, Dict[str, Any]]
        self.dividends: Dict[str, Dict[str, Any]]
        self.contributions: Dict[str, Dict[str, Any]]
        self.target_allocation: Dict[str, Any]
        self.rmd_info: Dict[str, Any]
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
        self.target_allocation = scenario.get("target_allocation", DEFAULT_STATE_COPY["target_allocation"])
        self.rmd_info = scenario.get("rmd_info", DEFAULT_STATE_COPY["rmd_info"])

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
                                suggested_action="Use find_stocks() to find valid fund IDs.")
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

    def get_stock_price(self, fund_id: str) -> Dict[str, Any]:
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

    def find_stocks(
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

    def get_holdings(self) -> Dict[str, Any]:
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

    def get_order_placement(self, order_id: str) -> Dict[str, Any]:
        """
        Get order details.

        Args:
            order_id (str): The order identifier.

        Returns:
            Dict[str, Any]: Full order record.
        """
        order = self._require_order(order_id)
        return deepcopy(order)

    def list_order_placements(self, limit: int = 20) -> List[Dict[str, Any]]:
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

    def watchlist_add_symbol(self, symbol: str) -> Dict[str, Any]:
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

    def watchlist_remove_symbol(self, symbol: str) -> Dict[str, Any]:
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

    def watchlist_list(self) -> List[Dict[str, Any]]:
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

    # -----------------------------------------------------------------------
    # Portfolio Rebalancing
    # -----------------------------------------------------------------------

    def get_target_allocation(self) -> Dict[str, Any]:
        """
        Get the target asset allocation percentages.

        Returns:
            Dict[str, Any]: stocks_percent (float), bonds_percent (float),
                cash_percent (float).
        """
        if not self.target_allocation:
            return {
                "stocks_percent": 0,
                "bonds_percent": 0,
                "cash_percent": 0,
                "status": "not_set",
            }
        return deepcopy(self.target_allocation)

    def set_target_allocation(
        self, stocks_percent: float, bonds_percent: float, cash_percent: float,
    ) -> Dict[str, Any]:
        """
        Set the target asset allocation. Percentages must sum to 100.

        Args:
            stocks_percent (float): Target percentage for stocks.
            bonds_percent (float): Target percentage for bonds.
            cash_percent (float): Target percentage for cash.

        Returns:
            Dict[str, Any]: stocks_percent (float), bonds_percent (float),
                cash_percent (float), status (str "set").
        """
        total = stocks_percent + bonds_percent + cash_percent
        if abs(total - 100) > 0.01:
            raise VanguardError(
                "INVALID_ALLOCATION",
                f"Allocation must sum to 100, got {total}.",
                context={"total": total},
            )
        for val, name in [(stocks_percent, "stocks"), (bonds_percent, "bonds"), (cash_percent, "cash")]:
            if val < 0:
                raise VanguardError("NEGATIVE_ALLOCATION", f"{name}_percent cannot be negative.")

        self.target_allocation = {
            "stocks_percent": stocks_percent,
            "bonds_percent": bonds_percent,
            "cash_percent": cash_percent,
            "status": "set",
        }
        return deepcopy(self.target_allocation)

    def get_rebalance_preview(self) -> Dict[str, Any]:
        """
        Preview trades needed to reach the target allocation.

        Returns:
            Dict[str, Any]: current_allocation (dict), target_allocation (dict),
                suggested_trades (List[Dict]) each with action (buy/sell),
                asset_class, amount.
        """
        if not self.target_allocation or self.target_allocation.get("status") == "not_set":
            raise VanguardError("NO_TARGET_SET", "Set a target allocation first.",
                                suggested_action="Use set_target_allocation() first.")

        positions_data = self.get_holdings()
        total_value = positions_data.get("total_value", 0)
        cash = self.profile.get("cash_balance", 0)
        grand_total = total_value + cash

        if grand_total <= 0:
            raise VanguardError("NO_PORTFOLIO_VALUE", "Portfolio has no value to rebalance.")

        # Classify positions into stocks/bonds
        stock_value = 0.0
        bond_value = 0.0
        for fid, pos in positions_data.get("positions", {}).items():
            fund = self.portfolio.get(fid, {})
            sector = fund.get("sector", "").lower()
            if "bond" in sector or "fixed income" in sector:
                bond_value += pos.get("current_value", 0)
            else:
                stock_value += pos.get("current_value", 0)

        current = {
            "stocks_percent": round(stock_value / grand_total * 100, 2) if grand_total else 0,
            "bonds_percent": round(bond_value / grand_total * 100, 2) if grand_total else 0,
            "cash_percent": round(cash / grand_total * 100, 2) if grand_total else 0,
        }

        target = self.target_allocation
        trades = []
        for asset_class, current_key, target_key in [
            ("stocks", "stocks_percent", "stocks_percent"),
            ("bonds", "bonds_percent", "bonds_percent"),
            ("cash", "cash_percent", "cash_percent"),
        ]:
            diff = target.get(target_key, 0) - current.get(current_key, 0)
            amount = round(abs(diff) / 100 * grand_total, 2)
            if abs(diff) > 0.5:
                trades.append({
                    "action": "buy" if diff > 0 else "sell",
                    "asset_class": asset_class,
                    "amount": amount,
                    "current_percent": current.get(current_key, 0),
                    "target_percent": target.get(target_key, 0),
                })

        return {
            "current_allocation": current,
            "target_allocation": {
                "stocks_percent": target.get("stocks_percent", 0),
                "bonds_percent": target.get("bonds_percent", 0),
                "cash_percent": target.get("cash_percent", 0),
            },
            "grand_total": grand_total,
            "suggested_trades": trades,
        }

    def execute_rebalance(self) -> Dict[str, Any]:
        """
        Execute rebalancing trades to reach the target allocation.

        Returns:
            Dict[str, Any]: status (str), orders_placed (List[Dict]) each
                with order_id, fund_id, side, amount.
        """
        preview = self.get_rebalance_preview()
        orders_placed = []

        for trade in preview.get("suggested_trades", []):
            asset_class = trade.get("asset_class")
            action = trade.get("action")
            amount = trade.get("amount", 0)

            if asset_class == "cash":
                continue

            # Pick a representative fund for the asset class
            target_fund = None
            for fid, fund in self.portfolio.items():
                sector = fund.get("sector", "").lower()
                if asset_class == "bonds" and ("bond" in sector or "fixed income" in sector):
                    target_fund = fid
                    break
                elif asset_class == "stocks" and "bond" not in sector and "fixed income" not in sector:
                    if fid in self.positions:
                        target_fund = fid
                        break

            if not target_fund:
                for fid, fund in self.portfolio.items():
                    sector = fund.get("sector", "").lower()
                    if asset_class == "stocks" and "bond" not in sector and "fixed income" not in sector:
                        target_fund = fid
                        break

            if target_fund and amount > 0:
                if action == "buy":
                    result = self.buy_fund(target_fund, amount)
                    orders_placed.append({
                        "order_id": result["order_id"],
                        "fund_id": target_fund,
                        "side": "buy",
                        "amount": amount,
                    })
                elif action == "sell":
                    result = self.sell_fund(target_fund, amount=amount)
                    orders_placed.append({
                        "order_id": result["order_id"],
                        "fund_id": target_fund,
                        "side": "sell",
                        "amount": result.get("proceeds", amount),
                    })

        return {"status": "completed", "orders_placed": orders_placed}

    # -----------------------------------------------------------------------
    # RMD Calculator
    # -----------------------------------------------------------------------

    def calculate_rmd(
        self,
        account_id: Optional[str] = None,
        birth_date: Optional[str] = None,
        account_balance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculate Required Minimum Distribution using IRS life expectancy
        tables.

        Args:
            account_id (str, optional): Account identifier. Defaults to
                current account.
            birth_date (str, optional): Date of birth (YYYY-MM-DD). Uses
                stored value if not provided.
            account_balance (float, optional): Account balance for calculation.
                Uses current portfolio value if not provided.

        Returns:
            Dict[str, Any]: age (int), life_expectancy_factor (float),
                account_balance (float), rmd_amount (float),
                deadline (str).
        """
        # Use stored birth_date if available
        bd = birth_date or self.rmd_info.get("birth_date")
        if not bd:
            raise VanguardError("BIRTH_DATE_REQUIRED",
                                "Birth date is required for RMD calculation.",
                                suggested_action="Provide birth_date parameter.")

        # Calculate age
        birth = datetime.strptime(bd, "%Y-%m-%d")
        today = datetime.now(timezone.utc)
        age = today.year - birth.year
        if (today.month, today.day) < (birth.month, birth.day):
            age -= 1

        if age < 73:
            return {
                "age": age,
                "rmd_required": False,
                "message": f"RMD not required until age 73. You are currently {age}.",
            }

        # Simplified IRS Uniform Lifetime Table
        life_table = {
            73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9,
            78: 22.0, 79: 21.1, 80: 20.2, 81: 19.4, 82: 18.5,
            83: 17.7, 84: 16.8, 85: 16.0, 86: 15.2, 87: 14.4,
            88: 13.7, 89: 12.9, 90: 12.2, 91: 11.5, 92: 10.8,
            93: 10.1, 94: 9.5, 95: 8.9, 96: 8.4, 97: 7.8,
            98: 7.3, 99: 6.8, 100: 6.4,
        }
        factor = life_table.get(age, life_table.get(100, 6.4))

        # Get balance
        if account_balance is not None:
            balance = account_balance
        else:
            positions_data = self.get_holdings()
            balance = positions_data.get("total_value", 0) + self.profile.get("cash_balance", 0)

        rmd_amount = round(balance / factor, 2)
        deadline = f"{today.year}-12-31"

        # Store in rmd_info
        self.rmd_info["birth_date"] = bd
        self.rmd_info["last_calculated_rmd"] = rmd_amount
        self.rmd_info["last_calculated_at"] = _utc_now_iso()

        return {
            "age": age,
            "life_expectancy_factor": factor,
            "account_balance": balance,
            "rmd_amount": rmd_amount,
            "deadline": deadline,
            "rmd_required": True,
        }

    def schedule_rmd_withdrawal(
        self, amount: float, frequency: str, start_date: str,
    ) -> Dict[str, Any]:
        """
        Schedule automatic RMD withdrawals.

        Args:
            amount (float): Amount per withdrawal.
            frequency (str): "monthly", "quarterly", or "annually".
            start_date (str): Start date (YYYY-MM-DD).

        Returns:
            Dict[str, Any]: schedule_id (str), amount (float),
                frequency (str), start_date (str), status (str "scheduled").
        """
        if amount <= 0:
            raise VanguardError("INVALID_AMOUNT", "Amount must be positive.")
        valid_freq = ("monthly", "quarterly", "annually")
        if frequency not in valid_freq:
            raise VanguardError("INVALID_FREQUENCY", f"Frequency must be one of {valid_freq}.")

        schedule_id = self._new_id("rmd_schedule")
        self.rmd_info["withdrawal_schedule"] = {
            "schedule_id": schedule_id,
            "amount": amount,
            "frequency": frequency,
            "start_date": start_date,
            "status": "scheduled",
            "created_at": _utc_now_iso(),
        }
        return {
            "schedule_id": schedule_id,
            "amount": amount,
            "frequency": frequency,
            "start_date": start_date,
            "status": "scheduled",
        }

    def get_rmd_status(self) -> Dict[str, Any]:
        """
        Check current RMD requirements and withdrawal schedule.

        Returns:
            Dict[str, Any]: birth_date (str | None),
                last_calculated_rmd (float | None),
                withdrawal_schedule (dict | None).
        """
        return {
            "birth_date": self.rmd_info.get("birth_date"),
            "last_calculated_rmd": self.rmd_info.get("last_calculated_rmd"),
            "last_calculated_at": self.rmd_info.get("last_calculated_at"),
            "withdrawal_schedule": deepcopy(self.rmd_info.get("withdrawal_schedule")),
        }
