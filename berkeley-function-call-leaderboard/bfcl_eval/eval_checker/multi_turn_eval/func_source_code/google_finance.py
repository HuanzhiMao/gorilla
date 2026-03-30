"""
Google Finance Dummy API (in-memory, deterministic, benchmark-friendly)

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


class GoogleFinanceError(Exception):
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


WINDOW_KEY_MAPPING = {
    "1D": "1d",
    "5D": "5d",
    "1M": "1mo",
    "6M": "6mo",
    "1Y": "1y",
}


DEFAULT_STATE = {
    "random_seed": 9101,
    "market_context": {},
    "quotes": {},
    "historical_data": {},
    "company_news": {},
    "analyst_views": {},
    "watchlists": {},
}


class GoogleFinanceAPI(PatchableMixin):
    """
    In-memory Google Finance style stock screener.

    State variables:
    - market_context: coverage metadata and defaults
    - quotes: Dict[symbol, quote/profile fields]
    - historical_data: Dict[symbol, Dict[window, List[data points]]]
    - company_news: Dict[symbol, List[news articles]]
    - analyst_views: Dict[symbol, analyst summary]
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
            "This tool belongs to the Google Finance market-data API, which "
            "provides stock screening, live quote snapshots, price charts, "
            "company news, analyst summaries, and saved watchlists."
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
        if not isinstance(value, GoogleFinanceAPI):
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
            raise GoogleFinanceError(
                "SYMBOL_NOT_FOUND",
                f"Symbol '{symbol}' was not found in Google Finance coverage.",
                suggested_action="Use search_google_tickers() to discover supported symbols.",
                context={"symbol": symbol},
            )
        return quote

    def _require_history(self, symbol: str, window: str) -> List[Dict[str, Any]]:
        history_key = WINDOW_KEY_MAPPING.get(window.upper(), window.lower())
        series = self.historical_data.get(symbol.upper(), {}).get(history_key)
        if not series:
            raise GoogleFinanceError(
                "WINDOW_NOT_SUPPORTED",
                f"Google Finance chart window '{window}' is unavailable for '{symbol}'.",
                suggested_action="Use one of: 1D, 5D, 1M, 6M, 1Y.",
                context={"symbol": symbol, "window": window},
            )
        return series

    def _require_analyst_view(self, symbol: str) -> Dict[str, Any]:
        analyst_view = self.analyst_views.get(symbol.upper())
        if not analyst_view:
            raise GoogleFinanceError(
                "ANALYST_DATA_UNAVAILABLE",
                f"No analyst summary is available for '{symbol}'.",
                suggested_action="Try another covered symbol.",
                context={"symbol": symbol},
            )
        return analyst_view

    def _validate_exchange(self, quote: Dict[str, Any], exchange: Optional[str]) -> None:
        if exchange and quote.get("exchange", "").upper() != exchange.upper():
            raise GoogleFinanceError(
                "EXCHANGE_MISMATCH",
                f"Symbol '{quote['symbol']}' is listed on {quote.get('exchange')}, not {exchange}.",
                suggested_action="Retry without the exchange filter or use the listed exchange.",
                context={"symbol": quote["symbol"], "exchange": exchange},
            )

    def _normalize_symbols(self, symbols: List[str]) -> List[str]:
        if not symbols:
            raise GoogleFinanceError(
                "EMPTY_SYMBOL_LIST",
                "At least one ticker symbol is required.",
                suggested_action="Provide one or more covered ticker symbols.",
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

    def search_google_tickers(
        self,
        query: str,
        exchange: Optional[str] = None,
        asset_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search Google Finance coverage for symbols matching a name or ticker.

        Args:
            query (str): Search text matched against symbol and company name.
            exchange (str, optional): Exchange filter such as "NASDAQ" or "NYSE".
            asset_type (str, optional): Asset type filter such as "equity" or "etf".
            limit (int): Maximum number of results.

        Returns:
            List[Dict[str, Any]]: Matching symbol summaries.
        """
        results = []
        for quote in self.quotes.values():
            if exchange and quote.get("exchange", "").upper() != exchange.upper():
                continue
            if asset_type and quote.get("asset_type") != asset_type:
                continue
            if _matches_query(quote.get("symbol", ""), query) or _matches_query(
                quote.get("name", ""), query
            ):
                results.append(
                    {
                        "symbol": quote["symbol"],
                        "name": quote["name"],
                        "exchange": quote["exchange"],
                        "asset_type": quote["asset_type"],
                        "current_price": quote["current_price"],
                        "day_change_percent": quote["day_change_percent"],
                    }
                )
        return results[:limit]

    def get_google_quote(
        self, symbol: str, exchange: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a live Google Finance style quote snapshot.

        Args:
            symbol (str): Ticker symbol.
            exchange (str, optional): Expected exchange.

        Returns:
            Dict[str, Any]: Quote and company snapshot fields for the symbol.
        """
        quote = self._require_quote(symbol)
        self._validate_exchange(quote, exchange)
        return deepcopy(quote)

    def get_google_price_chart(self, symbol: str, window: str = "1M") -> Dict[str, Any]:
        """
        Get a Google Finance chart window for a ticker.

        Args:
            symbol (str): Ticker symbol.
            window (str): One of 1D, 5D, 1M, 6M, 1Y.

        Returns:
            Dict[str, Any]: symbol, window, currency, market_state, points.
        """
        quote = self._require_quote(symbol)
        points = self._require_history(symbol, window)
        return {
            "symbol": quote["symbol"],
            "window": window.upper(),
            "currency": quote["currency"],
            "market_state": quote["market_state"],
            "points": deepcopy(points),
        }

    def get_google_company_news(
        self, symbol: str, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Get recent news stories for a company.

        Args:
            symbol (str): Ticker symbol.
            limit (int): Maximum number of articles.

        Returns:
            List[Dict[str, Any]]: Recent articles with title, source, timestamp, and summary.
        """
        self._require_quote(symbol)
        articles = self.company_news.get(symbol.upper(), [])
        return deepcopy(articles[:limit])

    def get_google_analyst_summary(self, symbol: str) -> Dict[str, Any]:
        """
        Get the analyst consensus summary for a ticker.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: Consensus rating, target price, upside, and rating breakdown.
        """
        return deepcopy(self._require_analyst_view(symbol))

    def get_google_company_profile(self, symbol: str) -> Dict[str, Any]:
        """
        Get descriptive company profile information.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: Company profile fields such as sector, industry, and description.
        """
        quote = self._require_quote(symbol)
        return {
            "symbol": quote["symbol"],
            "name": quote["name"],
            "exchange": quote["exchange"],
            "sector": quote["sector"],
            "industry": quote["industry"],
            "market_cap": quote["market_cap"],
            "pe_ratio": quote["pe_ratio"],
            "forward_pe": quote["forward_pe"],
            "peg_ratio": quote["peg_ratio"],
            "dividend_yield": quote["dividend_yield"],
            "week_52_low": quote["week_52_low"],
            "week_52_high": quote["week_52_high"],
            "week_52_range": {
                "low": quote["week_52_low"],
                "high": quote["week_52_high"],
            },
            "beta": quote["beta"],
            "headquarters": quote["headquarters"],
            "description": quote["description"],
        }

    def screen_google_equities(
        self,
        sector: Optional[str] = None,
        analyst_rating: Optional[str] = None,
        min_market_cap: Optional[float] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Screen equities by sector, analyst view, and minimum market cap.

        Args:
            sector (str, optional): Sector filter.
            analyst_rating (str, optional): Consensus rating filter.
            min_market_cap (float, optional): Minimum market capitalization.
            limit (int): Maximum results to return.

        Returns:
            List[Dict[str, Any]]: Matching screener rows sorted by market cap.
        """
        results = []
        for symbol, quote in self.quotes.items():
            if quote.get("asset_type") != "equity":
                continue
            if sector and quote.get("sector") != sector:
                continue
            if min_market_cap is not None and quote.get("market_cap", 0) < min_market_cap:
                continue
            analyst_view = self.analyst_views.get(symbol, {})
            consensus = analyst_view.get("consensus_rating", quote.get("analyst_rating"))
            if analyst_rating and consensus != analyst_rating:
                continue
            results.append(
                {
                    "symbol": quote["symbol"],
                    "name": quote["name"],
                    "sector": quote["sector"],
                    "industry": quote["industry"],
                    "current_price": quote["current_price"],
                    "market_cap": quote["market_cap"],
                    "dividend_yield": quote["dividend_yield"],
                    "consensus_rating": consensus,
                    "target_price": analyst_view.get("target_price", quote.get("target_price")),
                }
            )
        results.sort(key=lambda row: row["market_cap"], reverse=True)
        return results[:limit]

    def save_google_watchlist(self, name: str, symbols: List[str]) -> Dict[str, Any]:
        """
        Save a named Google Finance watchlist.

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

    def list_google_watchlists(self) -> List[Dict[str, Any]]:
        """
        List all saved Google Finance watchlists.

        Returns:
            List[Dict[str, Any]]: Saved watchlist records.
        """
        return [deepcopy(watchlist) for watchlist in self.watchlists.values()]
