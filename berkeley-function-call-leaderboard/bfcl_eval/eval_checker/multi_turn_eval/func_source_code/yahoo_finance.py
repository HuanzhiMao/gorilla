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
    "options_data": {},
    "conversations": {},
    "trending_tickers": [],
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
    - options_data: Dict[symbol, {expirations, chains}]
    - conversations: Dict[symbol, List[{post_id, text, timestamp}]]
    - trending_tickers: List[{symbol, mentions, sentiment}]
    """

    def __init__(self):
        self._id_counters = {}
        self.market_context: Dict[str, Any]
        self.quotes: Dict[str, Dict[str, Any]]
        self.historical_data: Dict[str, Dict[str, List[Dict[str, Any]]]]
        self.company_news: Dict[str, List[Dict[str, Any]]]
        self.analyst_views: Dict[str, Dict[str, Any]]
        self.watchlists: Dict[str, Dict[str, Any]]
        self.options_data: Dict[str, Dict[str, Any]]
        self.conversations: Dict[str, List[Dict[str, Any]]]
        self.trending_tickers: List[Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Yahoo Finance API, which provides "
            "ticker lookup, live quote data, historical price ranges, "
            "market news, recommendation trends, and saved watchlists."
        )

    def _load_scenario(
        self,
        scenario: Dict[str, Any],
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
        self.options_data = scenario.get("options_data", default_state["options_data"])
        self.conversations = scenario.get(
            "conversations", default_state["conversations"]
        )
        self.trending_tickers = scenario.get(
            "trending_tickers", default_state["trending_tickers"]
        )

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

    # ── Options Chain Data ──────────────────────────────────────────────

    def get_yahoo_options_chain(
        self, symbol: str, expiration_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get options chain data for a symbol.

        Args:
            symbol (str): Ticker symbol.
            expiration_date (str, optional): Expiration date to filter. If None returns the nearest expiration.

        Returns:
            Dict[str, Any]: Options chain with calls and puts including strike, premium,
                bid, ask, volume, open_interest, and implied_volatility.
        """
        self._require_quote(symbol)
        norm_symbol = symbol.upper()
        options = self.options_data.get(norm_symbol)
        if not options:
            raise YahooFinanceError(
                "OPTIONS_UNAVAILABLE",
                f"No options data is available for '{symbol}'.",
                suggested_action="Try a symbol with listed options.",
                context={"ticker": symbol},
            )
        expirations = options.get("expirations", [])
        chains = options.get("chains", {})
        if expiration_date:
            if expiration_date not in chains:
                raise YahooFinanceError(
                    "EXPIRATION_NOT_FOUND",
                    f"Expiration date '{expiration_date}' is not available for '{symbol}'.",
                    suggested_action="Use get_yahoo_options_expirations() to see available dates.",
                    context={"ticker": symbol, "expiration_date": expiration_date},
                )
            chain = chains[expiration_date]
        else:
            if not expirations:
                raise YahooFinanceError(
                    "OPTIONS_UNAVAILABLE",
                    f"No expiration dates available for '{symbol}'.",
                    suggested_action="Try a symbol with listed options.",
                    context={"ticker": symbol},
                )
            chain = chains.get(expirations[0], {"calls": [], "puts": []})
            expiration_date = expirations[0]
        return {
            "symbol": norm_symbol,
            "expiration_date": expiration_date,
            "calls": deepcopy(chain.get("calls", [])),
            "puts": deepcopy(chain.get("puts", [])),
        }

    def get_yahoo_options_expirations(self, symbol: str) -> Dict[str, Any]:
        """
        Get available options expiration dates for a symbol.

        Args:
            symbol (str): Ticker symbol.

        Returns:
            Dict[str, Any]: Symbol and list of available expiration dates.
        """
        self._require_quote(symbol)
        norm_symbol = symbol.upper()
        options = self.options_data.get(norm_symbol)
        if not options:
            raise YahooFinanceError(
                "OPTIONS_UNAVAILABLE",
                f"No options data is available for '{symbol}'.",
                suggested_action="Try a symbol with listed options.",
                context={"ticker": symbol},
            )
        return {
            "symbol": norm_symbol,
            "expirations": deepcopy(options.get("expirations", [])),
        }

    # ── Community Discussion ────────────────────────────────────────────

    def get_yahoo_conversations(
        self, symbol: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent community discussion posts for a symbol.

        Args:
            symbol (str): Ticker symbol.
            limit (int): Maximum number of posts to return.

        Returns:
            List[Dict[str, Any]]: Recent discussion posts.
        """
        self._require_quote(symbol)
        posts = self.conversations.get(symbol.upper(), [])
        return deepcopy(posts[:limit])

    def post_yahoo_comment(self, symbol: str, text: str) -> Dict[str, Any]:
        """
        Post a comment in the Yahoo Finance community discussion for a symbol.

        Args:
            symbol (str): Ticker symbol.
            text (str): Comment text.

        Returns:
            Dict[str, Any]: Posted comment with assigned post_id.
        """
        self._require_quote(symbol)
        norm_symbol = symbol.upper()
        post_id = f"ypost_{self._rng.randint(100000, 999999)}"
        comment = {
            "post_id": post_id,
            "symbol": norm_symbol,
            "text": text,
            "timestamp": _utc_now_iso(),
        }
        if norm_symbol not in self.conversations:
            self.conversations[norm_symbol] = []
        self.conversations[norm_symbol].insert(0, comment)
        return deepcopy(comment)

    def get_yahoo_trending_tickers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get tickers trending in Yahoo Finance community discussions.

        Args:
            limit (int): Maximum number of trending tickers to return.

        Returns:
            List[Dict[str, Any]]: Trending tickers with mention counts and sentiment.
        """
        return deepcopy(self.trending_tickers[:limit])
