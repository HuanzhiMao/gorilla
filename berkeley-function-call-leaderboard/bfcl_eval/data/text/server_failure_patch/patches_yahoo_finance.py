"""Runtime patches for YahooFinanceAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.yahoo_finance import YahooFinanceAPI, YahooFinanceError

# ─── Source: daud ───


@YahooFinanceAPI._register_patch("get_yahoo_live_quote", "priceless_schema_permanent")
def get_yahoo_live_quote_priceless_schema_permanent(self, symbol):
    quote = self._original_function(symbol)
    return {
        'symbol': quote['symbol'],
        'short_name': quote['short_name'],
        'exchange': quote['exchange'],
        'quote_type': quote['quote_type'],
        'currency': quote['currency'],
        'pctChange': quote['regular_market_change_percent'],
        'mktCap': quote['market_cap'],
        'volume': f"{quote['regular_market_volume']:,}",
    }


@YahooFinanceAPI._register_patch("list_yahoo_watchlists", "renewable_corrupted_permanent")
def list_yahoo_watchlists_renewable_corrupted_permanent(self):
    return [
        {'name': 'Renewable Energy', 'symbols': ['ENPH', '$$INVALID', 'FSLR'], 'created_at': '2026-03-24T09:00:00Z'},
        {'name': 'Renewable Energy', 'symbols': ['NEE', 'NULLTICKER', 'SEDG', 'NEE'], 'created_at': '2026-03-24T09:01:00Z'},
        {'name': 'Renewable Energy', 'symbols': ['ENPH', 'FSLR', '$$INVALID', '$$INVALID'], 'created_at': '2026-03-24T09:02:00Z'},
    ]


@YahooFinanceAPI._register_patch("get_yahoo_price_history", "price_history_stale_once")
def get_yahoo_price_history_price_history_stale_once(self, symbol, range='1mo', interval='1d'):
    result = self._original_function(symbol, range, interval)
    if self._patch_call_count == 1:
        result['prices'] = [
            {'date': '2026-02-27', 'close': result['prices'][0]['close'], 'volume': result['prices'][0]['volume']},
            {'date': '2026-03-04', 'close': result['prices'][1]['close'], 'volume': result['prices'][1]['volume']},
            {'date': '2026-03-10', 'close': result['prices'][2]['close'], 'volume': result['prices'][2]['volume']},
            {'date': '2026-03-12', 'close': result['prices'][3]['close'], 'volume': result['prices'][3]['volume']},
        ]
        result['last_updated'] = '2026-03-12T16:00:00Z'
    return result


# ─── Source: jason ───


@YahooFinanceAPI._register_patch("get_yahoo_live_quote", "edge_cache_timeout")
def get_yahoo_live_quote_edge_cache_timeout(self, symbol):

    if self._patch_call_count == 1:
        raise YahooFinanceError(
            error_code="EDGE_CACHE_TIMEOUT",
            message="Yahoo Finance edge cache timed out before the live quote response completed.",
            suggested_action="Retry the live quote call or switch to another finance server.",
            context={"ticker": symbol},
        )
    return self._original_function(symbol)


@YahooFinanceAPI._register_patch("get_yahoo_price_history", "stale_range_cache")
def get_yahoo_price_history_stale_range_cache(self, symbol, range="1mo", interval="1d"):
    result = self._original_function(symbol, range, interval)
    result["cached_at"] = "2026-03-17T14:00:00Z"
    if result.get("prices"):
        for point in result["prices"]:
            if "price" in point:
                point["price"] = round(point["price"] * 0.98, 2)
            if "close" in point:
                point["close"] = round(point["close"] * 0.98, 2)
    result["_stale_warning"] = "Historical range served from stale cache"
    return result


@YahooFinanceAPI._register_patch("save_yahoo_watchlist", "silent_watchlist_drop")
def save_yahoo_watchlist_silent_watchlist_drop(self, name, symbols):
    return {"name": name, "symbols": [symbol.upper() for symbol in symbols], "created_at": "2026-03-23T15:10:00Z"}


@YahooFinanceAPI._register_patch("get_yahoo_live_quote", "field_rename_schema")
def get_yahoo_live_quote_field_rename_schema(self, symbol):
    quote = self._original_function(symbol)
    return {
        "ticker": quote["symbol"],
        "last_price": quote["regular_market_price"],
        "pct_change": quote["regular_market_change_percent"],
        "avg_vol_3m": quote["average_daily_volume_3month"],
    }


@YahooFinanceAPI._register_patch("list_yahoo_watchlists", "corrupted_watchlist_index")
def list_yahoo_watchlists_corrupted_watchlist_index(self):
    return [
        {"name": "core_growth", "symbols": ["SPY", "SPY", "NVDA"], "created_at": "2026-03-20T19:10:00Z"},
        {"name": "broken_entry", "symbols": [], "created_at": "2026-03-20T19:11:00Z"},
    ]
