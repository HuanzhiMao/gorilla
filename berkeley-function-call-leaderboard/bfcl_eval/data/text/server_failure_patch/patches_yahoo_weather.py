"""Runtime patches for YahooWeatherAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.yahoo_weather import YahooWeatherAPI, YahooWeatherError
from copy import deepcopy

# ============================================================================
# S3: Yahoo Weather get_astronomy permanently down (GEO_INDEX_ERROR)
# Trigger: get_astronomy always raises GEO_INDEX_ERROR
# ============================================================================
@YahooWeatherAPI._register_patch("get_astronomy", "geo_index_error")
def get_astronomy_geo_index_error(self, location):
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
@YahooWeatherAPI._register_patch("get_5day_forecast", "placeholder_data")
def get_5day_forecast_placeholder_data(self, location, days=5):
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
@YahooWeatherAPI._register_patch("bookmark_location", "silent_write_drop_permanent")
def bookmark_location_silent_write_drop_permanent(self, label, location):
    return {"label": label, "location": location, "status": "added"}


# ============================================================================
# S23: Yahoo Weather get_pressure_trend requires fully-qualified location string
# Trigger: 1st call raises PARAMETER_RESTRUCTURED with a hint that maps to a
#          format the underlying function actually accepts (full 'City, State');
#          retry with the corrected value succeeds.
# ============================================================================
@YahooWeatherAPI._register_patch("get_pressure_trend", "parameter_restructured")
def get_pressure_trend_parameter_restructured(self, location):
    if self._patch_call_count == 1:
        raise YahooWeatherError(
            error_code="PARAMETER_RESTRUCTURED",
            message="Parameter 'location' must be a fully qualified 'City, State' string, not a bare city name.",
            suggested_action="Retry with location formatted as 'Denver, CO' (or the equivalent two-letter state code).",
            context={
                "expected_format": "<City>, <STATE>",
                "example": "Denver, CO",
            },
        )
    return self._original_function(location)


# ============================================================================
# S24: Yahoo Weather compare_weather rejects bare city names in the locations list
# Trigger: 1st call raises UNKNOWN_PARAMETER with a hint to supply fully
#          qualified 'City, State' strings inside the existing 'locations' list;
#          retry with the corrected values succeeds.
# ============================================================================
@YahooWeatherAPI._register_patch("compare_weather", "unknown_parameter")
def compare_weather_unknown_parameter(self, locations):
    if self._patch_call_count == 1:
        raise YahooWeatherError(
            error_code="UNKNOWN_PARAMETER",
            message="Unrecognized location entries in 'locations'. Each entry must be a fully qualified 'City, State' string.",
            suggested_action="Retry with locations like ['Boston, MA', 'Philadelphia, PA'] inside the existing 'locations' parameter.",
            context={
                "expected_format": "<City>, <STATE>",
                "example": ["Boston, MA", "Philadelphia, PA"],
            },
        )
    return self._original_function(locations)
