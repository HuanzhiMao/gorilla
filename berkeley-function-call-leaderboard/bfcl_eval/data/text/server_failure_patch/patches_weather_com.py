"""Runtime patches for WeatherComAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.weather_com import WeatherComAPI, WeatherComError

# ============================================================================
# S0: Weather.com upstream forecast provider times out transiently
# Trigger: get_hourly_forecast raises UPSTREAM_TIMEOUT on 1st call, succeeds on retry
# ============================================================================
@WeatherComAPI._register_patch("get_hourly_forecast", "UPSTREAM_TIMEOUT")
def s0_get_hourly_forecast(self, location, hours=48):

    if self._patch_call_count == 1:
        raise WeatherComError(
            error_code="UPSTREAM_TIMEOUT",
            message="Upstream forecast provider timed out. The request may succeed on retry.",
            suggested_action="Retry the request after a brief wait.",
            context={"location": location},
        )
    return self._original_function(location, hours)


# ============================================================================
# S1: Weather.com compare_locations feature permanently suspended
# Trigger: compare_locations always raises FEATURE_SUSPENDED
# ============================================================================
@WeatherComAPI._register_patch("compare_locations", "FEATURE_SUSPENDED")
def s1_compare_locations(self, locations):

    raise WeatherComError(
        error_code="FEATURE_SUSPENDED",
        message="The location comparison feature has been permanently suspended.",
        suggested_action="Use an alternative weather service for location comparisons.",
        context={},
    )


# ============================================================================
# S2: Weather.com alert API per-endpoint rate limit
# Trigger: get_alerts raises ENDPOINT_QUOTA_EXCEEDED on 1st call for Houston,
#          succeeds on retry
# ============================================================================
@WeatherComAPI._register_patch("get_alerts", "ENDPOINT_QUOTA_EXCEEDED")
def s2_get_alerts(self, location):

    if self._patch_call_count <= 1:
        raise WeatherComError(
            error_code="ENDPOINT_QUOTA_EXCEEDED",
            message="Per-endpoint rate limit exceeded. Resets in approximately 30 seconds.",
            suggested_action="Wait briefly and retry the request.",
            context={
                "location": location,
                "retry_after_seconds": 30,
            },
        )
    return self._original_function(location)


# ============================================================================
# S4: Weather.com get_alert_details fails for specific alert undergoing migration
# Trigger: get_alert_details always raises ALERT_RECORD_MIGRATING
# ============================================================================
@WeatherComAPI._register_patch("get_alert_details", "ALERT_RECORD_MIGRATING")
def s4_get_alert_details(self, location, alert_id):

    raise WeatherComError(
        error_code="ALERT_RECORD_MIGRATING",
        message=f"Alert record '{alert_id}' is currently being migrated to a new archival system.",
        suggested_action="Full alert details are temporarily unavailable. Check the National Weather Service website for the complete bulletin.",
        context={"alert_id": alert_id, "location": location},
    )


# ============================================================================
# S5: Weather.com weekend forecast cache is stale from days ago
# Trigger: get_daily_forecast returns stale data with old generated_at
# ============================================================================
@WeatherComAPI._register_patch("get_daily_forecast", "STALE_CACHE")
def s5_get_daily_forecast(self, location, days=10):
    result = self._original_function(location, days)
    result["generated_at"] = "2026-03-16T06:00:00Z"
    result["_stale_warning"] = "Data generated 4 days ago"
    for day in result.get("days", []):
        day["condition_day"] = "Sunny"
        day["condition_night"] = "Clear"
        day["precipitation_chance"] = 5
    return result


# ============================================================================
# S6: Weather.com current conditions stale from early morning; re-fetch corrects
# Trigger: 1st call returns stale data (Clear, from 6am), 2nd call returns fresh
# ============================================================================
@WeatherComAPI._register_patch("get_current_weather", "STALE_OBSERVATION")
def s6_get_current_weather(self, location):
    if self._patch_call_count == 1:
        return {
            "location": location,
            "observed_at": "2026-03-20T06:00:00Z",
            "condition": "Clear",
            "temperature": 55,
            "feels_like": 53,
            "humidity": 40,
            "wind": {"speed": 5, "direction": "W"},
            "precipitation": 0,
            "visibility": 10,
            "uv_index": 0,
        }
    return self._original_function(location)


# ============================================================================
# S7: Weather.com current wind observation permanently stale
# Trigger: get_current_weather always returns 6-hour-old stale data
# ============================================================================
@WeatherComAPI._register_patch("get_current_weather", "STALE_OBSERVATION_PERMANENT")
def s7_get_current_weather(self, location):
    return {
        "location": location,
        "observed_at": "2026-03-20T08:00:00Z",
        "condition": "Partly Cloudy",
        "temperature": 62,
        "feels_like": 60,
        "humidity": 55,
        "wind": {"speed": 8, "direction": "SW"},
        "precipitation": 0,
        "visibility": 10,
        "uv_index": 3,
        "_stale_warning": "Observation is 6 hours old",
    }


# ============================================================================
# S8: Weather.com pollen forecast returns last spring's seasonal data
# Trigger: get_daily_forecast returns data with year-old forecast_date
# ============================================================================
@WeatherComAPI._register_patch("get_daily_forecast", "STALE_SEASONAL_DATA")
def s8_get_daily_forecast(self, location, days=10):
    return {
        "location": location,
        "forecast_date": "2025-04-15",
        "generated_at": "2025-04-15T12:00:00Z",
        "days": [
            {
                "date": "2025-04-15",
                "condition_day": "Sunny",
                "temp_max": 82,
                "temp_min": 65,
                "pollen": {
                    "tree": "Very High",
                    "grass": "High",
                    "weed": "Moderate",
                    "overall": "Very High",
                },
                "precipitation_chance": 10,
            }
        ][: max(1, int(days))],
    }


# ============================================================================
# S10: Weather.com save_location silently drops one of two saves (temporary)
# Trigger: 1st call returns success but doesn't persist; retry works
# ============================================================================
@WeatherComAPI._register_patch("add_saved_location", "SILENT_WRITE_DROP")
def s10_add_saved_location(self, label, location):
    if self._patch_call_count == 1:
        return {"label": label, "location": location, "status": "added"}
    return self._original_function(label, location)


# ============================================================================
# S11: Weather.com remove_saved_location permanently returns success but never removes
# Trigger: remove_saved_location always returns success without removing
# ============================================================================
@WeatherComAPI._register_patch("remove_saved_location", "SILENT_DELETE_NOOP")
def s11_remove_saved_location(self, label):
    return {"label": label, "status": "removed"}


# ============================================================================
# S12/S13: Weather.com save_location permanently non-functional; all saves dropped
# Trigger: add_saved_location always returns success but never persists
# ============================================================================
@WeatherComAPI._register_patch("add_saved_location", "SILENT_WRITE_DROP_PERMANENT")
def s12_add_saved_location(self, label, location):
    return {"label": label, "location": location, "status": "added"}


# ============================================================================
# S14: Weather.com get_hourly_forecast returns partial data with zeroed placeholders
# Trigger: hours 3-6 have zero precipitation/wind values
# ============================================================================
@WeatherComAPI._register_patch("get_hourly_forecast", "ZERO_FILLED_PLACEHOLDER")
def s14_get_hourly_forecast(self, location, hours=48):
    result = self._original_function(location, hours)
    hour_list = result.get("hours", [])
    for i, hour in enumerate(hour_list):
        if i >= 2:
            hour["precipitation_chance"] = 0
            hour["precipitation_amount"] = 0
            hour["wind"] = {"speed": 0, "direction": "N"}
    return result


# ============================================================================
# S15: Weather.com location metadata index corrupted mid-session
# Trigger: get_hourly_forecast raises LOCATION_TOKEN_STALE on 1st call, succeeds on retry
# ============================================================================
@WeatherComAPI._register_patch("get_hourly_forecast", "LOCATION_TOKEN_STALE")
def s15_get_hourly_forecast(self, location, hours=48):

    if self._patch_call_count == 1:
        raise WeatherComError(
            error_code="LOCATION_TOKEN_STALE",
            message="Location token has expired. Re-resolve the location to obtain a fresh token.",
            suggested_action="Call search_location() again to get a fresh location token, then retry.",
            context={"location": location},
        )
    return self._original_function(location, hours)


# ============================================================================
# S16: Weather.com saved locations state corrupted by concurrent session
# Trigger: get_saved_locations returns different data each call
# ============================================================================
@WeatherComAPI._register_patch("get_saved_locations", "CONCURRENT_MODIFICATION")
def s16_get_saved_locations(self):
    call = self._patch_call_count
    if call == 1:
        return [
            {
                "label": "Home",
                "location": "New York",
                "temperature": 42,
                "condition": "Cloudy",
            },
            {
                "label": "Office",
                "location": "Chicago",
                "temperature": 38,
                "condition": "Snow",
            },
            {
                "label": "Vacation",
                "location": "Miami",
                "temperature": 79,
                "condition": "Sunny",
            },
        ]
    elif call == 2:
        return [
            {
                "label": "Home",
                "location": "New York",
                "temperature": 42,
                "condition": "Cloudy",
            },
            {
                "label": "Office",
                "location": "Chicago",
                "temperature": 38,
                "condition": "Snow",
            },
            {
                "label": "Gym",
                "location": "Boston",
                "temperature": 35,
                "condition": "Rain",
            },
        ]
    else:
        return [
            {
                "label": "Home",
                "location": "New York",
                "temperature": 42,
                "condition": "Cloudy",
            },
            {
                "label": "Commute",
                "location": "Philadelphia",
                "temperature": 40,
                "condition": "Overcast",
            },
        ]


# ============================================================================
# S17: Weather.com session context expires mid-workflow
# Trigger: get_historical_weather raises SESSION_CONTEXT_EXPIRED on 1st call, succeeds on retry
# ============================================================================
@WeatherComAPI._register_patch("get_historical_weather", "SESSION_CONTEXT_EXPIRED")
def s17_get_historical_weather(self, location, date):

    if self._patch_call_count == 1:
        raise WeatherComError(
            error_code="SESSION_CONTEXT_EXPIRED",
            message="Session context has expired. Re-resolve the location to refresh.",
            suggested_action="Call search_location() to refresh session context, then retry.",
            context={"location": location},
        )
    return self._original_function(location, date)


# ============================================================================
# S18: Weather.com search_location returns wrong city (Springfield, IL not MA)
# Trigger: get_current_weather returns data for Springfield, IL instead of MA
# ============================================================================
@WeatherComAPI._register_patch("get_current_weather", "GEO_INDEX_CORRUPTION")
def s18_get_current_weather(self, location):
    return {
        "location": "Springfield, IL",
        "observed_at": "2026-03-20T14:00:00Z",
        "condition": "Partly Cloudy",
        "temperature": 58,
        "feels_like": 55,
        "humidity": 45,
        "wind": {"speed": 12, "direction": "NW"},
        "precipitation": 0,
        "visibility": 10,
        "uv_index": 4,
        "state": "IL",
        "country": "US",
    }


# ============================================================================
# S19: Weather.com returns temperatures in Celsius despite US locale
# Trigger: get_current_weather returns Celsius values (e.g., 26 for Miami)
# ============================================================================
@WeatherComAPI._register_patch("get_current_weather", "UNIT_PREFERENCE_CORRUPTED")
def s19_get_current_weather(self, location):
    return {
        "location": location,
        "observed_at": "2026-03-20T14:00:00Z",
        "condition": "Sunny",
        "temperature": 26,
        "feels_like": 27,
        "humidity": 65,
        "wind": {"speed": 8, "direction": "SE"},
        "precipitation": 0,
        "visibility": 10,
        "uv_index": 8,
        "unit": "celsius",
    }


# ============================================================================
# S20: Weather.com get_air_quality expects numeric location index instead of string
# Trigger: get_air_quality raises PARAMETER_TYPE_MISMATCH on 1st call
# ============================================================================
@WeatherComAPI._register_patch("get_air_quality", "PARAMETER_TYPE_MISMATCH")
def s20_get_air_quality(self, location):

    if self._patch_call_count == 1:
        raise WeatherComError(
            error_code="PARAMETER_TYPE_MISMATCH",
            message="Parameter 'location' expected numeric location index, got string.",
            suggested_action="Call get_location() first to obtain the numeric_index for the location, then pass that as the location parameter.",
            context={
                "expected_type": "int",
                "received_type": "str",
                "received_value": location,
                "hint": "Use get_location(location_name) to resolve to numeric_index",
            },
        )
    return self._original_function(location)


# ============================================================================
# S21/S24: Weather.com compare_locations requires undocumented parameters
# Trigger: compare_locations always raises MISSING_REQUIRED_FIELD
# ============================================================================
@WeatherComAPI._register_patch("compare_locations", "MISSING_REQUIRED_FIELD")
def s21_compare_locations(self, locations):

    if self._patch_call_count == 1:
        raise WeatherComError(
            error_code="MISSING_REQUIRED_FIELD",
            message="Required field 'metrics' is missing. Specify which metrics to compare.",
            suggested_action="Add metrics=['temperature','humidity','wind'] parameter.",
            context={"missing_field": "metrics"},
        )
    elif self._patch_call_count == 2:
        raise WeatherComError(
            error_code="INVALID_PARAMETER_FORMAT",
            message="Parameter 'locations' must be a comma-separated string, not a list.",
            suggested_action="Pass locations as 'Portland,Denver,Phoenix' instead of a list.",
            context={},
        )
    raise WeatherComError(
        error_code="INTERNAL_SCHEMA_ERROR",
        message="The compare_locations endpoint is experiencing persistent schema incompatibility.",
        suggested_action="Use an alternative weather service for location comparisons.",
        context={},
    )


# ============================================================================
# S22: Weather.com get_historical_weather requires undocumented date format
# Trigger: get_historical_weather raises cascading schema errors
# ============================================================================
@WeatherComAPI._register_patch("get_historical_weather", "DATE_FORMAT_INVALID")
def s22_get_historical_weather(self, location, date):

    if self._patch_call_count == 1:
        raise WeatherComError(
            error_code="DATE_FORMAT_INVALID",
            message="Date parameter must use compact format 'YYYYMMDD', not ISO-8601.",
            suggested_action="Use format like '20250615' instead of '2025-06-15'.",
            context={},
        )
    elif self._patch_call_count == 2:
        raise WeatherComError(
            error_code="MISSING_REQUIRED_FIELD",
            message="Required field 'metrics' is missing for historical queries.",
            suggested_action="Add metrics=['temp_high','temp_low','precipitation'] parameter.",
            context={},
        )
    raise WeatherComError(
        error_code="FIELD_NAME_INVALID",
        message="Unknown field 'metrics'. Did you mean 'data_fields'?",
        suggested_action="The historical weather API schema appears incompatible with documentation. Try an alternative data source.",
        context={},
    )
