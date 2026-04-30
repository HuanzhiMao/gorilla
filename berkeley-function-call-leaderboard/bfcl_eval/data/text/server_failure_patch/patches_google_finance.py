"""Runtime patches for GoogleFinanceAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.google_finance import GoogleFinanceAPI, GoogleFinanceError

# ─── Source: daud ───


@GoogleFinanceAPI._register_patch("get_google_quote", "quote_endpoint_gone_permanent")
def get_google_quote_quote_endpoint_gone_permanent(self, symbol, exchange=None):
    raise GoogleFinanceError(
        error_code='ENDPOINT_GONE',
        message='HTTP 410 Gone. This Google Finance quote endpoint has been permanently discontinued.',
        suggested_action='Use another stock screener for current quote data.',
        context={'symbol': symbol, 'http_status': 410},
    )


@GoogleFinanceAPI._register_patch("get_google_price_chart", "stale_six_weeks_permanent")
def get_google_price_chart_stale_six_weeks_permanent(self, symbol, window='1M'):
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


@GoogleFinanceAPI._register_patch("get_google_quote", "semi_schema_shift_permanent")
def get_google_quote_semi_schema_shift_permanent(self, symbol, exchange=None):
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


@GoogleFinanceAPI._register_patch("get_google_analyst_summary", "semi_schema_shift_permanent")
def get_google_analyst_summary_semi_schema_shift_permanent(self, symbol):
    if symbol.upper() not in {'AVGO', 'QCOM', 'MRVL'}:
        return self._original_function(symbol)
    raise GoogleFinanceError(
        error_code='FEATURE_DISABLED',
        message='Google Finance analyst summaries are temporarily unavailable for this migrated semiconductor quote surface.',
        suggested_action='Use the same alternate market-data provider for both prices and analyst ratings.',
        context={'symbol': symbol},
    )


# ─── Source: jason ───


@GoogleFinanceAPI._register_patch("get_google_quote", "upstream_timeout")
def get_google_quote_upstream_timeout(self, symbol, exchange=None):

    if self._patch_call_count == 1:
        raise GoogleFinanceError(
            error_code="UPSTREAM_TIMEOUT",
            message="Google Finance quote provider timed out before returning the latest snapshot.",
            suggested_action="Retry the quote request or switch to another market-data service.",
            context={"symbol": symbol},
        )
    return self._original_function(symbol, exchange)


@GoogleFinanceAPI._register_patch("get_google_price_chart", "stale_chart_cache")
def get_google_price_chart_stale_chart_cache(self, symbol, window="1M"):
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


@GoogleFinanceAPI._register_patch("save_google_watchlist", "silent_watchlist_drop")
def save_google_watchlist_silent_watchlist_drop(self, name, symbols):
    return {"name": name, "symbols": [symbol.upper() for symbol in symbols], "created_at": "2026-03-23T15:00:00Z"}


@GoogleFinanceAPI._register_patch("get_google_quote", "quote_schema_shift")
def get_google_quote_quote_schema_shift(self, symbol, exchange=None):
    quote = self._original_function(symbol, exchange)
    return {
        "ticker": quote["symbol"],
        "last": quote["current_price"],
        "chg": quote["day_change"],
        "chgPct": quote["day_change_percent"],
        "mktCap": quote["market_cap"],
    }


@GoogleFinanceAPI._register_patch("list_google_watchlists", "corrupted_watchlist_index")
def list_google_watchlists_corrupted_watchlist_index(self):
    return [
        {"name": "ai_leaders", "symbols": ["AAPL", "NVDA", "ZZZZ"], "created_at": "2026-03-20T18:15:00Z"},
        {"name": "ai_leaders", "symbols": ["MSFT"], "created_at": "2026-03-20T18:16:00Z"},
    ]


# ---------- get_google_price_chart (stale_chart_feed_temporary) ----------


# ft_extra_43 -- data_staleness/temporary. First call returns a chart
# whose 'last_updated' is from 2 weeks ago and whose data points stop on
# 2026-04-12; second call falls through to the live chart.
@GoogleFinanceAPI._register_patch("get_google_price_chart", "stale_chart_feed_temporary")
def get_google_price_chart_stale_chart_feed_temporary(self, symbol, window="1M", *args, **kwargs):
    """Temporary. First call returns a chart payload whose last_updated is
    2 weeks stale and whose data points are truncated to ones <= 2026-04-12.
    Second call falls through unchanged."""
    if self._patch_call_count <= 1:
        chart = self._original_function(symbol, window, *args, **kwargs)
        if isinstance(chart, dict):
            chart["last_updated"] = "2026-04-12T16:00:00Z"
            chart["stale_snapshot"] = True
            data = chart.get("data") or chart.get("points") or []
            if isinstance(data, list):
                cutoff = "2026-04-12"
                trimmed = [
                    p for p in data
                    if not isinstance(p, dict) or (p.get("date") or "") <= cutoff
                ]
                if "data" in chart:
                    chart["data"] = trimmed
                if "points" in chart:
                    chart["points"] = trimmed
        return chart
    return self._original_function(symbol, window, *args, **kwargs)
