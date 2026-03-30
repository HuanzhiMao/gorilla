"""
Yahoo Finance Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- General market-data focus so it can act as a fungible stock screener.
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .server_patch_mixin import PatchableMixin


class YahooFinanceError(Exception):
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _matches_query(text: str, query: str) -> bool:
    q = (query or "").strip().lower()
    return not q or q in (text or "").lower()


DEFAULT_STATE = {
    "random_seed": 9102,
    "market_context": {},
    "quotes": {},
    "historical_data": {},
    "company_news": {},
    "analyst_views": {},
    "watchlists": {},
}


class YahooFinanceAPI(PatchableMixin):
    """
    In-memory Yahoo Finance style market data server.

    State variables:
    - market_context: coverage metadata and defaults
    - quotes: Dict[symbol, quote/profile fields]
    - historical_data: Dict[symbol, Dict[range, List[data points]]]
    - company_news: Dict[symbol, List[news articles]]
    - analyst_views: Dict[symbol, recommendation summaries]
    - watchlists: Dict[name, {name, symbols, created_at}]
    """

    def __init__(self):
        self._id_counters = {}
        self.market_context: Dict[str, Any]
        self.quotes: Dict[str, Dict[str, Any]]
        self.historical_data: Dict[str, Dict[str, List[Dict[str, Any]]]]
        self.company_news: Dict[str, List[Dict[str, Any]]]
        self.analyst_views: Dict[str, Dict[str, Any]]
        self.watchlists: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Yahoo Finance API, which provides "
            "ticker lookup, live quote data, historical price ranges, "
            "market news, recommendation trends, and saved watchlists."
        )

    def _load_scenario(
        self,
        scenario: Dict[str, Any],
        long_context: bool = False,
    ) -> None:
        default_state = deepcopy(DEFAULT_STATE)
        self._rng = random.Random(
            scenario.get("random_seed", default_state["random_seed"])
        )
        self.market_context = scenario.get(
            "market_context", default_state["market_context"]
        )
        self.quotes = scenario.get("quotes", default_state["quotes"])
        self.historical_data = scenario.get(
            "historical_data", default_state["historical_data"]
        )
        self.company_news = scenario.get(
            "company_news", default_state["company_news"]
        )
        self.analyst_views = scenario.get(
            "analyst_views", default_state["analyst_views"]
        )
        self.watchlists = scenario.get("watchlists", default_state["watchlists"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, YahooFinanceAPI):
            return False
        for attr_name in vars(self):
            if attr_name.startswith("_"):
                continue
            if getattr(self, attr_name) != getattr(value, attr_name):
                return False
        return True

    def _require_quote(self, symbol: str) -> Dict[str, Any]:
        quote = self.quotes.get(symbol.upper())
        if not quote:
            raise YahooFinanceError(
                "TICKER_NOT_FOUND",
                f"Ticker '{symbol}' was not found in Yahoo Finance coverage.",
                suggested_action="Use search_yahoo_tickers() to discover supported tickers.",
                context={"ticker": symbol},
            )
        return quote

    def _require_range(self, symbol: str, range_value: str) -> List[Dict[str, Any]]:
        series = self.historical_data.get(symbol.upper(), {}).get(range_value.lower())
        if not series:
            raise YahooFinanceError(
                "RANGE_NOT_SUPPORTED",
                f"Yahoo Finance range '{range_value}' is unavailable for '{symbol}'.",
                suggested_action="Use one of: 1d, 5d, 1mo, 6mo, 1y.",
                context={"ticker": symbol, "range": range_value},
            )
        return series

    def _require_recommendations(self, symbol: str) -> Dict[str, Any]:
        view = self.analyst_views.get(symbol.upper())
        if not view:
            raise YahooFinanceError(
                "RECOMMENDATIONS_UNAVAILABLE",
                f"No recommendation trend is available for '{symbol}'.",
                suggested_action="Try another covered ticker.",
                context={"ticker": symbol},
            )
        return view

    def _normalize_symbols(self, symbols: List[str]) -> List[str]:
        if not symbols:
            raise YahooFinanceError(
                "EMPTY_TICKER_LIST",
                "At least one ticker is required.",
                suggested_action="Provide one or more supported tickers.",
            )
        normalized = []
        seen = set()
        for symbol in symbols:
            normalized_symbol = symbol.upper()
            self._require_quote(normalized_symbol)
            if normalized_symbol not in seen:
                normalized.append(normalized_symbol)
                seen.add(normalized_symbol)
        return normalized

    def search_yahoo_tickers(
        self,
        query: str,
        quote_type: Optional[str] = None,
        exchange: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search Yahoo Finance coverage for tickers matching a name or symbol.

        Args:
            query (str): Search text matched against symbol and company name.
            quote_type (str, optional): Asset type filter such as "equity" or "etf".
            exchange (str, optional): Exchange filter such as "NASDAQ" or "NYSE".
            limit (int): Maximum number of rows to return.

        Returns:
            List[Dict[str, Any]]: Matching Yahoo Finance style search rows.
        """
        results = []
        for quote in self.quotes.values():
            if quote_type and quote.get("asset_type") != quote_type:
                continue
            if exchange and quote.get("exchange", "").upper() != exchange.upper():
                continue
            if _matches_query(quote.get("symbol", ""), query) or _matches_query(
                quote.get("name", ""), query
            ):
                results.append(
                    {
                        "symbol": quote["symbol"],
                        "short_name": quote["name"],
                        "quote_type": quote["asset_type"],
                        "exchange": quote["exchange"],
                        "regular_market_price": quote["current_price"],
                        "regular_market_change_percent": quote["day_change_percent"],
                    }
                )
        return results[:limit]

    def get_yahoo_live_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get a Yahoo Finance live quote snapshot.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: Quote snapshot with market and company fields.
        """
        quote = self._require_quote(symbol)
        return {
            "symbol": quote["symbol"],
            "short_name": quote["name"],
            "exchange": quote["exchange"],
            "quote_type": quote["asset_type"],
            "currency": quote["currency"],
            "regular_market_price": quote["current_price"],
            "regular_market_previous_close": quote["previous_close"],
            "regular_market_change": quote["day_change"],
            "regular_market_change_percent": quote["day_change_percent"],
            "market_cap": quote["market_cap"],
            "regular_market_volume": quote["volume"],
            "average_daily_volume_3month": quote["average_volume"],
            "market_state": quote["market_state"],
            "sector": quote["sector"],
            "industry": quote["industry"],
        }

    def get_yahoo_price_history(
        self, symbol: str, range: str = "1mo", interval: str = "1d"
    ) -> Dict[str, Any]:
        """
        Get Yahoo Finance style historical prices for a range and interval.

        Args:
            symbol (str): Ticker symbol.
            range (str): One of 1d, 5d, 1mo, 6mo, 1y.
            interval (str): Interval label echoed back in the response.

        Returns:
            Dict[str, Any]: symbol, range, interval, prices.
        """
        quote = self._require_quote(symbol)
        prices = self._require_range(symbol, range)
        return {
            "symbol": quote["symbol"],
            "range": range.lower(),
            "interval": interval,
            "currency": quote["currency"],
            "prices": deepcopy(prices),
        }

    def get_yahoo_company_news(
        self, symbol: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recent Yahoo Finance market news for a ticker.

        Args:
            symbol (str): Ticker symbol.
            limit (int): Maximum number of articles.

        Returns:
            List[Dict[str, Any]]: Recent articles for the ticker.
        """
        self._require_quote(symbol)
        return deepcopy(self.company_news.get(symbol.upper(), [])[:limit])

    def get_yahoo_recommendation_trend(self, symbol: str) -> Dict[str, Any]:
        """
        Get the Yahoo Finance recommendation trend summary for a ticker.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: Recommendation trend, target price, and analyst count.
        """
        return deepcopy(self._require_recommendations(symbol))

    def get_yahoo_company_profile(self, symbol: str) -> Dict[str, Any]:
        """
        Get descriptive company information for a ticker.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: Company profile fields.
        """
        quote = self._require_quote(symbol)
        return {
            "symbol": quote["symbol"],
            "short_name": quote["name"],
            "exchange": quote["exchange"],
            "sector": quote["sector"],
            "industry": quote["industry"],
            "market_cap": quote["market_cap"],
            "beta": quote["beta"],
            "trailing_pe": quote["pe_ratio"],
            "forward_pe": quote["forward_pe"],
            "peg_ratio": quote["peg_ratio"],
            "dividend_yield": quote["dividend_yield"],
            "fifty_two_week_low": quote["week_52_low"],
            "fifty_two_week_high": quote["week_52_high"],
            "long_business_summary": quote["description"],
            "city": quote["headquarters"],
        }

    def screen_yahoo_equities(
        self,
        sector: Optional[str] = None,
        analyst_rating: Optional[str] = None,
        min_market_cap: Optional[float] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Screen equities by sector, analyst view, and market capitalization.

        Args:
            sector (str, optional): Sector filter.
            analyst_rating (str, optional): Recommendation filter.
            min_market_cap (float, optional): Minimum market capitalization.
            limit (int): Maximum number of rows.

        Returns:
            List[Dict[str, Any]]: Matching screener rows.
        """
        rows = []
        for symbol, quote in self.quotes.items():
            if quote.get("asset_type") != "equity":
                continue
            if sector and quote.get("sector") != sector:
                continue
            if min_market_cap is not None and quote.get("market_cap", 0) < min_market_cap:
                continue
            recommendations = self.analyst_views.get(symbol, {})
            consensus = recommendations.get(
                "consensus_rating", quote.get("analyst_rating")
            )
            if analyst_rating and consensus != analyst_rating:
                continue
            rows.append(
                {
                    "symbol": quote["symbol"],
                    "short_name": quote["name"],
                    "sector": quote["sector"],
                    "industry": quote["industry"],
                    "regular_market_price": quote["current_price"],
                    "market_cap": quote["market_cap"],
                    "dividend_yield": quote["dividend_yield"],
                    "recommendation_key": consensus,
                    "target_mean_price": recommendations.get(
                        "target_price", quote.get("target_price")
                    ),
                }
            )
        rows.sort(key=lambda row: row["market_cap"], reverse=True)
        return rows[:limit]

    def save_yahoo_watchlist(self, name: str, symbols: List[str]) -> Dict[str, Any]:
        """
        Save a named Yahoo Finance watchlist.

        Args:
            name (str): Watchlist name.
            symbols (List[str]): Ticker symbols to include.

        Returns:
            Dict[str, Any]: Saved watchlist metadata.
        """
        normalized = self._normalize_symbols(symbols)
        self.watchlists[name] = {
            "name": name,
            "symbols": normalized,
            "created_at": _utc_now_iso(),
        }
        return deepcopy(self.watchlists[name])

    def list_yahoo_watchlists(self) -> List[Dict[str, Any]]:
        """
        List all saved Yahoo Finance watchlists.

        Returns:
            List[Dict[str, Any]]: Saved watchlist records.
        """
        return [deepcopy(watchlist) for watchlist in self.watchlists.values()]
