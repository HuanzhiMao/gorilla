"""Runtime patches for YelpAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.yelp import YelpAPI, YelpError

@YelpAPI._register_patch("search_businesses", "rate_limited_temporary")
def search_businesses_rate_limited_temporary(self, *args, **kwargs):
    """Temporary. Fails on first call with RATE_LIMITED, passes through on 2nd+."""
    if self._patch_call_count <= 1:
        raise YelpError(
            "RATE_LIMITED",
            "Yelp API rate limit exceeded. Please retry after a brief wait.",
            "Wait a moment and retry.",
        )
    return self._original_function(*args, **kwargs)


# ft_extra_53 -- data_staleness/temporary. First call returns a stale
# business-feed snapshot whose 'updated_at' values are all 30+ days old
# (and one entry references a business that has since closed). Second
# call falls through to the live data.
@YelpAPI._register_patch("search_businesses", "stale_business_feed_temporary")
def search_businesses_stale_business_feed_temporary(self, *args, **kwargs):
    """Temporary. First call stamps every result with a stale_snapshot
    marker and rewrites updated_at to a 35-day-old timestamp. Second call
    falls through unchanged."""
    if self._patch_call_count <= 1:
        results = self._original_function(*args, **kwargs)
        for r in results:
            if isinstance(r, dict):
                r["updated_at"] = "2026-03-22T08:00:00Z"
                r["stale_snapshot"] = True
        return results
    return self._original_function(*args, **kwargs)
