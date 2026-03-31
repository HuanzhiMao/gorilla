"""Runtime patches for YelpAPI methods."""

from mfcl_eval.eval_checker.multi_turn_eval.func_source_code.yelp import YelpAPI, YelpError

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
