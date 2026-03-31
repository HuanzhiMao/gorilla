"""
Alpha Vantage Dummy API (in-memory, deterministic, benchmark-friendly)

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


class AlphaVantageError(Exception):
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
    "random_seed": 9103,
    "market_context": {},
    "quotes": {},
    "historical_data": {},
    "company_news": {},
    "analyst_views": {},
    "watchlists": {},
}


class AlphaVantageAPI(PatchableMixin):
    """
    In-memory Alpha Vantage style market data server.

    State variables:
    - market_context: coverage metadata and defaults
    - quotes: Dict[symbol, quote/profile fields]
    - historical_data: Dict[symbol, Dict[interval, List[data points]]]
    - company_news: Dict[symbol, List[news articles]]
    - analyst_views: Dict[symbol, rating snapshots]
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
            "This tool belongs to the Alpha Vantage market-data API, which "
            "provides symbol search, global quote snapshots, time series "
            "history, news sentiment, company overviews, and saved watchlists."
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
        if not isinstance(value, AlphaVantageAPI):
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
            raise AlphaVantageError(
                "INVALID_SYMBOL",
                f"Alpha Vantage does not have market data for '{symbol}'.",
                suggested_action="Use search_alpha_symbols() to discover supported tickers.",
                context={"symbol": symbol},
            )
        return quote

    def _require_interval(self, symbol: str, interval: str) -> List[Dict[str, Any]]:
        series = self.historical_data.get(symbol.upper(), {}).get(interval.lower())
        if not series:
            raise AlphaVantageError(
                "INVALID_INTERVAL",
                f"Time series interval '{interval}' is unavailable for '{symbol}'.",
                suggested_action="Use one of: daily, weekly, monthly.",
                context={"symbol": symbol, "interval": interval},
            )
        return series

    def _require_rating_snapshot(self, symbol: str) -> Dict[str, Any]:
        view = self.analyst_views.get(symbol.upper())
        if not view:
            raise AlphaVantageError(
                "SNAPSHOT_UNAVAILABLE",
                f"No rating snapshot is available for '{symbol}'.",
                suggested_action="Try another covered symbol.",
                context={"symbol": symbol},
            )
        return view

    def _normalize_symbols(self, symbols: List[str]) -> List[str]:
        if not symbols:
            raise AlphaVantageError(
                "EMPTY_SYMBOL_LIST",
                "At least one symbol is required.",
                suggested_action="Provide one or more covered symbols.",
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

    def search_alpha_symbols(
        self,
        keywords: str,
        exchange: Optional[str] = None,
        asset_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search Alpha Vantage symbol coverage by keywords.

        Args:
            keywords (str): Search text matched against symbol and company name.
            exchange (str, optional): Exchange filter such as "NASDAQ" or "NYSE".
            asset_type (str, optional): Asset type filter such as "equity" or "etf".
            limit (int): Maximum number of rows to return.

        Returns:
            List[Dict[str, Any]]: Matching symbol search rows.
        """
        rows = []
        for quote in self.quotes.values():
            if exchange and quote.get("exchange", "").upper() != exchange.upper():
                continue
            if asset_type and quote.get("asset_type") != asset_type:
                continue
            if _matches_query(quote.get("symbol", ""), keywords) or _matches_query(
                quote.get("name", ""), keywords
            ):
                rows.append(
                    {
                        "symbol": quote["symbol"],
                        "name": quote["name"],
                        "exchange": quote["exchange"],
                        "asset_type": quote["asset_type"],
                        "currency": quote["currency"],
                        "match_score": quote.get("match_score", "0.95"),
                    }
                )
        return rows[:limit]

    def get_alpha_global_quote(self, symbol: str) -> Dict[str, Any]:
        """
        Get an Alpha Vantage GLOBAL_QUOTE style snapshot.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: Global quote style response fields.
        """
        quote = self._require_quote(symbol)
        return {
            "01. symbol": quote["symbol"],
            "02. open": quote["previous_close"],
            "03. high": round(quote["current_price"] * 1.01, 2),
            "04. low": round(quote["current_price"] * 0.99, 2),
            "05. price": quote["current_price"],
            "06. volume": quote["volume"],
            "07. latest trading day": self.market_context.get("latest_trading_day", "2026-03-23"),
            "08. previous close": quote["previous_close"],
            "09. change": quote["day_change"],
            "10. change percent": f"{quote['day_change_percent']}%",
        }

    def get_alpha_time_series(
        self, symbol: str, interval: str = "daily", outputsize: str = "compact"
    ) -> Dict[str, Any]:
        """
        Get Alpha Vantage style time series data.

        Args:
            symbol (str): Ticker symbol.
            interval (str): One of daily, weekly, monthly.
            outputsize (str): compact or full.

        Returns:
            Dict[str, Any]: symbol, interval, outputsize, series.
        """
        quote = self._require_quote(symbol)
        series = self._require_interval(symbol, interval)
        if outputsize not in {"compact", "full"}:
            raise AlphaVantageError(
                "INVALID_OUTPUTSIZE",
                "outputsize must be either 'compact' or 'full'.",
                suggested_action="Retry with outputsize='compact' or outputsize='full'.",
                context={"outputsize": outputsize},
            )
        points = series[:5] if outputsize == "compact" else series
        return {
            "symbol": quote["symbol"],
            "interval": interval.lower(),
            "outputsize": outputsize,
            "series": deepcopy(points),
        }

    def get_alpha_news_sentiment(
        self, symbol: str, limit: int = 5
    ) -> Dict[str, Any]:
        """
        Get Alpha Vantage style market news and sentiment for a symbol.

        Args:
            symbol (str): Ticker symbol.
            limit (int): Maximum number of articles.

        Returns:
            Dict[str, Any]: symbol, overall_sentiment, and feed articles.
        """
        self._require_quote(symbol)
        feed = deepcopy(self.company_news.get(symbol.upper(), [])[:limit])
        sentiment_score = 0.0
        if feed:
            sentiment_score = round(
                sum(article.get("sentiment_score", 0.0) for article in feed) / len(feed),
                3,
            )
        return {
            "symbol": symbol.upper(),
            "overall_sentiment_score": sentiment_score,
            "feed": feed,
        }

    def get_alpha_rating_snapshot(self, symbol: str) -> Dict[str, Any]:
        """
        Get a compact analyst-style rating snapshot for a symbol.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: Consensus rating, target price, and rating counts.
        """
        return deepcopy(self._require_rating_snapshot(symbol))

    def get_alpha_company_overview(self, symbol: str) -> Dict[str, Any]:
        """
        Get an Alpha Vantage COMPANY_OVERVIEW style summary.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: Company overview metrics and descriptive fields.
        """
        quote = self._require_quote(symbol)
        return {
            "Symbol": quote["symbol"],
            "Name": quote["name"],
            "Exchange": quote["exchange"],
            "AssetType": quote["asset_type"],
            "Sector": quote["sector"],
            "Industry": quote["industry"],
            "MarketCapitalization": quote["market_cap"],
            "PERatio": quote["pe_ratio"],
            "ForwardPE": quote["forward_pe"],
            "PEGRatio": quote["peg_ratio"],
            "DividendYield": quote["dividend_yield"],
            "52WeekLow": quote["week_52_low"],
            "52WeekHigh": quote["week_52_high"],
            "Beta": quote["beta"],
            "Description": quote["description"],
            "Address": quote["headquarters"],
        }

    def screen_alpha_equities(
        self,
        sector: Optional[str] = None,
        analyst_rating: Optional[str] = None,
        min_market_cap: Optional[float] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Screen equities by sector, analyst snapshot, and market capitalization.

        Args:
            sector (str, optional): Sector filter.
            analyst_rating (str, optional): Consensus rating filter.
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
            rating_snapshot = self.analyst_views.get(symbol, {})
            consensus = rating_snapshot.get(
                "consensus_rating", quote.get("analyst_rating")
            )
            if analyst_rating and consensus != analyst_rating:
                continue
            rows.append(
                {
                    "symbol": quote["symbol"],
                    "name": quote["name"],
                    "sector": quote["sector"],
                    "industry": quote["industry"],
                    "price": quote["current_price"],
                    "market_cap": quote["market_cap"],
                    "dividend_yield": quote["dividend_yield"],
                    "consensus_rating": consensus,
                    "target_price": rating_snapshot.get(
                        "target_price", quote.get("target_price")
                    ),
                }
            )
        rows.sort(key=lambda row: row["market_cap"], reverse=True)
        return rows[:limit]

    def save_alpha_watchlist(self, name: str, symbols: List[str]) -> Dict[str, Any]:
        """
        Save a named Alpha Vantage watchlist.

        Args:
            name (str): Watchlist name.
            symbols (List[str]): Symbols to include.

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

    def list_alpha_watchlists(self) -> List[Dict[str, Any]]:
        """
        List all saved Alpha Vantage watchlists.

        Returns:
            List[Dict[str, Any]]: Saved watchlist records.
        """
        return [deepcopy(watchlist) for watchlist in self.watchlists.values()]
