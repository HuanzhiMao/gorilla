"""Runtime patches for GoogleFinanceAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.google_finance import GoogleFinanceAPI, GoogleFinanceError

# ─── Source: daud ───


@GoogleFinanceAPI._register_patch("get_google_quote", "QUOTE_ENDPOINT_GONE_PERMANENT")
def patch_quote_gone(self, symbol, exchange=None):
    raise GoogleFinanceError(
        error_code='ENDPOINT_GONE',
        message='HTTP 410 Gone. This Google Finance quote endpoint has been permanently discontinued.',
        suggested_action='Use another stock screener for current quote data.',
        context={'symbol': symbol, 'http_status': 410},
    )


@GoogleFinanceAPI._register_patch("get_google_price_chart", "STALE_SIX_WEEKS_PERMANENT")
def patch_stale_chart(self, symbol, window='1M'):
    result = self._original_function(symbol, window)
    if symbol.upper() in {'ENPH', 'FSLR'}:
        result['points'] = [
            {'date': '2026-01-12', 'close': 92.15 if symbol.upper() == 'ENPH' else 178.4, 'volume': 4110000},
            {'date': '2026-01-19', 'close': 94.02 if symbol.upper() == 'ENPH' else 180.1, 'volume': 3980000},
            {'date': '2026-01-26', 'close': 95.61 if symbol.upper() == 'ENPH' else 182.7, 'volume': 4050000},
            {'date': '2026-02-02', 'close': 96.84 if symbol.upper() == 'ENPH' else 184.2, 'volume': 4120000},
            {'date': '2026-02-09', 'close': 97.33 if symbol.upper() == 'ENPH' else 185.6, 'volume': 4200000},
        ]
        result['cached_at'] = '2026-02-09T16:00:00Z'
    return result


@GoogleFinanceAPI._register_patch("get_google_quote", "SEMI_SCHEMA_SHIFT_PERMANENT")
def patch_schema_shift(self, symbol, exchange=None):
    quote = self._original_function(symbol, exchange)
    if symbol.upper() not in {'AVGO', 'QCOM', 'MRVL'}:
        return quote
    return {
        'symbol': quote['symbol'],
        'short_name': quote['name'],
        'market_snapshot': {'last_trade': {'value': quote['current_price']}},
        'denomination': quote['currency'],
        'analyst_rating': quote['analyst_rating'],
        'market_cap': quote['market_cap'],
    }


# ─── Source: jason ───


@GoogleFinanceAPI._register_patch("get_google_quote", "UPSTREAM_TIMEOUT")
def get_google_quote_upstream_timeout(self, symbol, exchange=None):

    if self._patch_call_count == 1:
        raise GoogleFinanceError(
            error_code="UPSTREAM_TIMEOUT",
            message="Google Finance quote provider timed out before returning the latest snapshot.",
            suggested_action="Retry the quote request or switch to another market-data service.",
            context={"symbol": symbol},
        )
    return self._original_function(symbol, exchange)


@GoogleFinanceAPI._register_patch("get_google_price_chart", "STALE_CHART_CACHE")
def get_google_price_chart_stale(self, symbol, window="1M"):
    result = self._original_function(symbol, window)
    result["generated_at"] = "2026-03-18T15:00:00Z"
    if result.get("points"):
        for point in result["points"]:
            if "price" in point:
                point["price"] = round(point["price"] * 0.97, 2)
            if "close" in point:
                point["close"] = round(point["close"] * 0.97, 2)
    result["_stale_warning"] = "Chart cache is 5 days old"
    return result


@GoogleFinanceAPI._register_patch("save_google_watchlist", "SILENT_WATCHLIST_DROP")
def save_google_watchlist_silent(self, name, symbols):
    return {"name": name, "symbols": [symbol.upper() for symbol in symbols], "created_at": "2026-03-23T15:00:00Z"}


@GoogleFinanceAPI._register_patch("get_google_quote", "QUOTE_SCHEMA_SHIFT")
def get_google_quote_schema(self, symbol, exchange=None):
    quote = self._original_function(symbol, exchange)
    return {
        "ticker": quote["symbol"],
        "last": quote["current_price"],
        "chg": quote["day_change"],
        "chgPct": quote["day_change_percent"],
        "mktCap": quote["market_cap"],
    }


@GoogleFinanceAPI._register_patch("list_google_watchlists", "CORRUPTED_WATCHLIST_INDEX")
def list_google_watchlists_corrupted(self):
    return [
        {"name": "ai_leaders", "symbols": ["AAPL", "NVDA", "ZZZZ"], "created_at": "2026-03-20T18:15:00Z"},
        {"name": "ai_leaders", "symbols": ["MSFT"], "created_at": "2026-03-20T18:16:00Z"},
    ]
