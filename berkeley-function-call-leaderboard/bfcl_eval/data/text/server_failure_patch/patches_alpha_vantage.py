"""Runtime patches for AlphaVantageAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.alpha_vantage import AlphaVantageAPI, AlphaVantageError

# ─── Source: daud ───


@AlphaVantageAPI._register_patch("get_alpha_time_series", "stale_window_permanent")
def get_alpha_time_series_stale_window_permanent(self, symbol, interval='daily', outputsize='compact'):
    result = self._original_function(symbol, interval, outputsize)
    if symbol.upper() in {'TSLA', 'AMZN'}:
        result['series'] = [
            {'date': '2026-02-25', 'open': 203.2, 'high': 205.4, 'low': 201.8, 'close': 204.6, 'volume': 101200000},
            {'date': '2026-02-26', 'open': 205.1, 'high': 206.8, 'low': 202.4, 'close': 203.7, 'volume': 97300000},
            {'date': '2026-02-27', 'open': 203.9, 'high': 207.2, 'low': 203.1, 'close': 206.4, 'volume': 95600000},
            {'date': '2026-03-02', 'open': 206.7, 'high': 209.0, 'low': 205.9, 'close': 208.1, 'volume': 99800000},
            {'date': '2026-03-03', 'open': 208.4, 'high': 210.6, 'low': 207.5, 'close': 209.8, 'volume': 102400000},
        ]
        result['refreshed_at'] = '2026-03-03T16:00:00Z'
        result['cache_status'] = 'stale'
    return result


@AlphaVantageAPI._register_patch("save_alpha_watchlist", "silent_save_noop_permanent")
def save_alpha_watchlist_silent_save_noop_permanent(self, name, symbols):
    return {
        'status': 'success',
        'watchlist_id': 'wl_9283',
        'name': name,
        'symbols': [symbol.upper() for symbol in symbols],
        'created_at': '2026-03-24T11:12:00Z',
    }


@AlphaVantageAPI._register_patch("get_alpha_global_quote", "rate_limited_temporary")
def get_alpha_global_quote_rate_limited_temporary(self, symbol):
    if self._patch_call_count == 1:
        raise AlphaVantageError(
            error_code='RATE_LIMITED_ENDPOINT',
            message='HTTP 429 Too Many Requests. Alpha Vantage temporary per-minute quota exceeded.',
            suggested_action='Retry this endpoint after the retry_after_seconds window.',
            context={'symbol': symbol, 'retry_after_seconds': 20},
        )
    return self._original_function(symbol)


@AlphaVantageAPI._register_patch("get_alpha_company_overview", "rate_limited_temporary")
def get_alpha_company_overview_rate_limited_temporary(self, symbol):
    if self._patch_call_count == 1:
        raise AlphaVantageError(
            error_code='RATE_LIMITED_ENDPOINT',
            message='HTTP 429 Too Many Requests. Alpha Vantage company overview quota exceeded.',
            suggested_action='Retry this endpoint after the retry_after_seconds window.',
            context={'symbol': symbol, 'retry_after_seconds': 20},
        )
    return self._original_function(symbol)


@AlphaVantageAPI._register_patch("list_alpha_watchlists", "winter_travel_corrupted_once")
def list_alpha_watchlists_winter_travel_corrupted_once(self):
    if self._patch_call_count == 1:
        return [
            {'name': 'Winter Travel Stocks', 'symbols': ['D@L', 'UDALxNT', 'M14CR', 'HLT', 'ABNB'], 'created_at': '2026-03-24T10:55:00Z'},
        ]
    return self._original_function()


# ─── Source: jason ───


@AlphaVantageAPI._register_patch("get_alpha_global_quote", "rate_limited_endpoint")
def get_alpha_global_quote_rate_limited_endpoint(self, symbol):
    if self._patch_call_count == 1:
        raise AlphaVantageError(
            error_code="RATE_LIMITED_ENDPOINT",
            message="Alpha Vantage GLOBAL_QUOTE hit a per-minute rate limit.",
            suggested_action="Retry after a short delay or switch to another stock screener.",
            context={"symbol": symbol, "retry_after_seconds": 12},
        )
    return self._original_function(symbol)


@AlphaVantageAPI._register_patch("get_alpha_time_series", "stale_series_snapshot")
def get_alpha_time_series_stale_series_snapshot(self, symbol, interval="daily", outputsize="compact"):
    result = self._original_function(symbol, interval, outputsize)
    result["refreshed_at"] = "2026-03-18T09:00:00Z"
    if result.get("series"):
        for point in result["series"]:
            if "close" in point:
                point["close"] = round(point["close"] * 0.985, 2)
    result["_stale_warning"] = "Time series snapshot is stale"
    return result


@AlphaVantageAPI._register_patch("save_alpha_watchlist", "silent_watchlist_drop")
def save_alpha_watchlist_silent_watchlist_drop(self, name, symbols):
    return {"name": name, "symbols": [symbol.upper() for symbol in symbols], "created_at": "2026-03-23T15:20:00Z"}


@AlphaVantageAPI._register_patch("get_alpha_global_quote", "legacy_global_quote_schema")
def get_alpha_global_quote_legacy_global_quote_schema(self, symbol):
    quote = self._original_function(symbol)
    return {
        "symbol": quote["01. symbol"],
        "price": quote["05. price"],
        "prev_close": quote["08. previous close"],
        "change_pct": quote["10. change percent"],
    }


@AlphaVantageAPI._register_patch("list_alpha_watchlists", "corrupted_watchlist_index")
def list_alpha_watchlists_corrupted_watchlist_index(self):
    return [
        {"name": "macro_watch", "symbols": ["MSFT", "SPY", "NULL"], "created_at": "2026-03-20T20:05:00Z"},
        {"name": "macro_watch", "symbols": ["JPM"], "created_at": "2026-03-20T20:06:00Z"},
    ]
