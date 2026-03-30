"""Runtime patches for YahooWeatherAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.yahoo_weather import YahooWeatherAPI, YahooWeatherError
from copy import deepcopy

# ============================================================================
# S3: Yahoo Weather get_astronomy permanently down (GEO_INDEX_ERROR)
# Trigger: get_astronomy always raises GEO_INDEX_ERROR
# ============================================================================
@YahooWeatherAPI._register_patch("get_astronomy", "GEO_INDEX_ERROR")
def s3_get_astronomy(self, location):
    raise YahooWeatherError(
        error_code="GEO_INDEX_ERROR",
        message="Geographic index lookup failed. The astronomy data service is currently unavailable.",
        suggested_action="Try an alternative weather service or a dedicated astronomy app.",
        context={"location": location},
    )


# ============================================================================
# S9: Yahoo Weather get_daily_forecast returns only 3 real days;
#     days 4-5 are duplicated placeholders of day 3
# Trigger: get_daily_forecast returns data with duplicate trailing days
# ============================================================================
@YahooWeatherAPI._register_patch("get_daily_forecast", "PLACEHOLDER_DATA")
def s9_get_daily_forecast(self, location, days=5):
    result = self._original_function(location, days)
    day_list = result.get("days", [])
    if len(day_list) >= 3:
        placeholder = deepcopy(day_list[2])
        while len(day_list) < 5:
            day_list.append(deepcopy(placeholder))
        for i in range(3, len(day_list)):
            day_list[i] = deepcopy(placeholder)
    result["days"] = day_list[:days]
    return result


# ============================================================================
# S13: Yahoo Weather add_saved_location permanently non-functional
# Trigger: add_saved_location always returns success but never persists
# ============================================================================
@YahooWeatherAPI._register_patch("add_saved_location", "SILENT_WRITE_DROP_PERMANENT")
def s13_add_saved_location(self, label, location):
    return {"label": label, "location": location, "status": "added"}


# ============================================================================
# S23: Yahoo Weather get_pressure_trend requires compound location-plus-date parameter
# Trigger: 1st call raises PARAMETER_RESTRUCTURED with hint; retry succeeds
# ============================================================================
@YahooWeatherAPI._register_patch("get_pressure_trend", "PARAMETER_RESTRUCTURED")
def s23_get_pressure_trend(self, location):
    if self._patch_call_count == 1:
        raise YahooWeatherError(
            error_code="PARAMETER_RESTRUCTURED",
            message="Parameter 'location' now requires compound format 'location_id:YYYY-MM-DD'.",
            suggested_action="Pass location as 'woeid_denver:2026-03-20' instead of just the location ID.",
            context={
                "expected_format": "<location_id>:<date>",
                "example": "woeid_denver:2026-03-04",
            },
        )
    return self._original_function(location)


# ============================================================================
# S24: Yahoo Weather compare_locations has undocumented parameter name
# Trigger: 1st call raises UNKNOWN_PARAMETER with hint to use 'woeid_list';
#          retry succeeds
# ============================================================================
@YahooWeatherAPI._register_patch("compare_locations", "UNKNOWN_PARAMETER")
def s24_compare_locations(self, locations):
    if self._patch_call_count == 1:
        raise YahooWeatherError(
            error_code="UNKNOWN_PARAMETER",
            message="Unknown parameter 'locations'. Did you mean 'woeid_list'?",
            suggested_action="Use parameter name 'woeid_list' instead of 'locations'.",
            context={
                "unknown_param": "locations",
                "suggested_param": "woeid_list",
            },
        )
    return self._original_function(locations)
