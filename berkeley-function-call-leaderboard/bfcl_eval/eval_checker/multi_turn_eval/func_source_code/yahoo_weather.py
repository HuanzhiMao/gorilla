"""
Yahoo Weather Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Simpler weather service: current, 12h hourly, 5-day forecast.
- Astronomy data (sunrise, sunset, moon phase), pressure trends, wind details.
- NO AQI, NO UV index, NO precipitation radar (differentiator from weather.com).
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .server_patch_mixin import PatchableMixin


class YahooWeatherError(Exception):
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
    "random_seed": 9002,
    "profile": {},
    "current_weather": {},
    "hourly_forecast": {},
    "daily_forecast": {},
    "alerts": {},
    "historical_weather": {},
    "location_index": {},
}


class YahooWeatherAPI(PatchableMixin):
    """
    In-memory dummy Yahoo Weather — simpler weather service.

    State variables:
    - profile: {default_location?, saved_locations[{label, location}],
      unit{temperature, wind, precipitation, distance}, timezone?}
    - current_weather: Dict of {location -> {location, observed_at,
      condition, temperature, feels_like, humidity, wind{speed, direction},
      precipitation?, visibility?, uv_index?}}
    - hourly_forecast: Dict of {location -> {location,
      hours[{time, condition, temperature, feels_like?,
      precipitation_chance?, precipitation_amount?,
      wind{speed, direction}?}]}}
    - daily_forecast: Dict of {location -> {location,
      days[{date, condition_day, condition_night?, temp_min, temp_max,
      precipitation_chance?, precipitation_amount?, sunrise?, sunset?}]}}
    - alerts: Dict of {location -> {location,
      alerts[{alert_id, event, severity, start_time, end_time,
      description}]}}
    - historical_weather: Dict of {location -> {date -> {location, date,
      condition, temp_high, temp_low, precipitation}}}
    - location_index: Dict of {location_name -> {woeid, name, state,
      country, lat, lon}}

    Yahoo Weather model: simpler weather with current conditions,
    12-hour hourly forecasts, 5-day daily forecasts, astronomy data
    (moon phases), pressure trends, wind details, historical weather
    data, and location resolution. No AQI, no UV index, no precipitation
    radar.
    """


    def __init__(self):
        self._id_counters = {}
        self.profile: Dict[str, Any]
        self.current_weather: Dict[str, Dict[str, Any]]
        self.hourly_forecast: Dict[str, Dict[str, Any]]
        self.daily_forecast: Dict[str, Dict[str, Any]]
        self.alerts: Dict[str, Dict[str, Any]]
        self.historical_weather: Dict[str, Dict[str, Dict[str, Any]]]
        self.location_index: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Yahoo Weather API, which provides "
            "current observations, 12-hour hourly and 5-day forecasts, "
            "astronomy data with moon phases, pressure trends, wind "
            "details, historical weather data, and location resolution."
        )

    def _load_scenario(
        self,
        scenario: Dict[str, Any],
        long_context: bool = False,
    ) -> None:
        """
        Load a scenario from the scenarios folder.
        Args:
            scenario (Dict[str, Any]): The scenario to load
        """
        DEFAULT_STATE_COPY = deepcopy(DEFAULT_STATE)
        self._rng = random.Random(
            scenario.get("random_seed", DEFAULT_STATE_COPY["random_seed"])
        )
        self.profile = scenario.get("profile", DEFAULT_STATE_COPY["profile"])
        self.current_weather = scenario.get(
            "current_weather", DEFAULT_STATE_COPY["current_weather"]
        )
        self.hourly_forecast = scenario.get(
            "hourly_forecast", DEFAULT_STATE_COPY["hourly_forecast"]
        )
        self.daily_forecast = scenario.get(
            "daily_forecast", DEFAULT_STATE_COPY["daily_forecast"]
        )
        self.alerts = scenario.get("alerts", DEFAULT_STATE_COPY["alerts"])
        self.historical_weather = scenario.get(
            "historical_weather", DEFAULT_STATE_COPY["historical_weather"]
        )
        self.location_index = scenario.get(
            "location_index", DEFAULT_STATE_COPY["location_index"]
        )
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, YahooWeatherAPI):
            return False

        for attr_name in vars(self):
            if attr_name.startswith("_"):
                continue
            model_attr = getattr(self, attr_name)
            ground_truth_attr = getattr(value, attr_name)

            if model_attr != ground_truth_attr:
                return False

        return True

    # ---- Internal ----

    def _require_current_weather(self, location: str) -> Dict[str, Any]:
        cw = self.current_weather.get(location)
        if not cw:
            raise YahooWeatherError(
                "LOCATION_NOT_FOUND",
                f"No weather data for location '{location}'.",
                suggested_action="Check the location name.",
            )
        return cw

    # ---- Location Resolution ----

    def search_location(self, query: str) -> Dict[str, Any]:
        """
        Search for a location by name, returns WOEID-style metadata.

        Args:
            query (str): Location name or partial match.

        Returns:
            Dict[str, Any]: woeid, name, state, country, lat, lon.
        """
        for loc_name, meta in self.location_index.items():
            if _matches_query(loc_name, query):
                return deepcopy(meta)
        raise YahooWeatherError(
            "LOCATION_NOT_FOUND",
            f"No location matching '{query}'.",
            suggested_action="Check spelling or try a different query.",
        )

    # ---- Profile ----

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get the current user's weather profile.

        Returns:
            Dict[str, Any]: default_location, saved_locations, unit, timezone.
        """
        return deepcopy(self.profile)

    def set_default_location(self, location: str) -> Dict[str, Any]:
        """
        Set the default location for weather queries.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: default_location, status.
        """
        self.profile["default_location"] = location
        return {"default_location": location, "status": "updated"}

    def add_saved_location(self, label: str, location: str) -> Dict[str, Any]:
        """
        Add a location to saved locations list.

        Args:
            label (str): Display label (e.g. "Home", "Office").
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: label, location, status "added".
        """
        saved = self.profile.setdefault("saved_locations", [])
        for s in saved:
            if s.get("label") == label:
                raise YahooWeatherError(
                    "LABEL_EXISTS",
                    f"Saved location with label '{label}' already exists.",
                )
        saved.append({"label": label, "location": location})
        return {"label": label, "location": location, "status": "added"}

    def remove_saved_location(self, label: str) -> Dict[str, Any]:
        """
        Remove a saved location by label.

        Args:
            label (str): The label of the saved location to remove.

        Returns:
            Dict[str, Any]: label, status "removed".
        """
        saved = self.profile.get("saved_locations", [])
        new_list = [s for s in saved if s.get("label") != label]
        if len(new_list) == len(saved):
            raise YahooWeatherError(
                "LABEL_NOT_FOUND", f"Saved location '{label}' not found."
            )
        self.profile["saved_locations"] = new_list
        return {"label": label, "status": "removed"}

    def get_saved_locations(self) -> List[Dict[str, Any]]:
        """
        Get all saved locations with current weather summary.

        Returns:
            List[Dict[str, Any]]: Saved locations with label, location,
                and current temperature/condition if available.
        """
        saved = self.profile.get("saved_locations", [])
        results = []
        for s in saved:
            loc = s.get("location", "")
            cw = self.current_weather.get(loc, {})
            results.append(
                {
                    "label": s.get("label"),
                    "location": loc,
                    "temperature": cw.get("temperature"),
                    "condition": cw.get("condition"),
                }
            )
        return results

    def set_unit_preferences(
        self,
        temperature: Optional[str] = None,
        wind: Optional[str] = None,
        precipitation: Optional[str] = None,
        distance: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Set measurement unit preferences.

        Args:
            temperature (str, optional): "fahrenheit" or "celsius".
            wind (str, optional): "mph" or "kph".
            precipitation (str, optional): "inches" or "mm".
            distance (str, optional): "miles" or "km".

        Returns:
            Dict[str, Any]: Updated unit preferences.
        """
        unit = self.profile.setdefault("unit", {})
        if temperature is not None:
            unit["temperature"] = temperature
        if wind is not None:
            unit["wind"] = wind
        if precipitation is not None:
            unit["precipitation"] = precipitation
        if distance is not None:
            unit["distance"] = distance
        return deepcopy(unit)

    # ---- Current Observation ----

    def get_current_weather(self, location: str) -> Dict[str, Any]:
        """
        Get current weather observation for a location.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location, observed_at, condition, temperature,
                feels_like, humidity, wind{speed, direction}, precipitation,
                visibility, uv_index.
        """
        return deepcopy(self._require_current_weather(location))

    # ---- Hourly Forecast (12 hours max) ----

    def get_hourly_forecast(self, location: str, hours: int = 12) -> Dict[str, Any]:
        """
        Get hourly forecast up to 12 hours.

        Args:
            location (str): Location name or identifier.
            hours (int): Number of hours (1-12). Defaults to 12.

        Returns:
            Dict[str, Any]: location, hours (list of hourly forecasts, each
                with time, condition, temperature, feels_like,
                precipitation_chance, precipitation_amount, wind{speed, direction}).
        """
        if hours < 1 or hours > 12:
            raise YahooWeatherError(
                "INVALID_HOURS",
                "Hours must be between 1 and 12.",
                suggested_action="Yahoo Weather supports up to 12 hours. Use Weather.com for 48h.",
            )
        forecast = self.hourly_forecast.get(location)
        if not forecast:
            raise YahooWeatherError(
                "LOCATION_NOT_FOUND", f"No hourly forecast for location '{location}'."
            )
        result = deepcopy(forecast)
        result["hours"] = result.get("hours", [])[:hours]
        return result

    # ---- Daily Forecast (5 days max) ----

    def get_daily_forecast(self, location: str, days: int = 5) -> Dict[str, Any]:
        """
        Get daily forecast up to 5 days.

        Args:
            location (str): Location name or identifier.
            days (int): Number of days (1-5). Defaults to 5.

        Returns:
            Dict[str, Any]: location, days (list of daily forecasts, each
                with date, condition_day, condition_night, temp_min, temp_max,
                precipitation_chance, precipitation_amount, sunrise, sunset).
        """
        if days < 1 or days > 5:
            raise YahooWeatherError(
                "INVALID_DAYS",
                "Days must be between 1 and 5.",
                suggested_action="Yahoo Weather supports up to 5 days. Use Weather.com for 10 days.",
            )
        forecast = self.daily_forecast.get(location)
        if not forecast:
            raise YahooWeatherError(
                "LOCATION_NOT_FOUND", f"No daily forecast for location '{location}'."
            )
        result = deepcopy(forecast)
        result["days"] = result.get("days", [])[:days]
        return result

    # ---- Alerts ----

    def get_alerts(self, location: str) -> Dict[str, Any]:
        """
        Get active weather alerts for a location.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location, alerts (list of alert objects, each
                with alert_id, event, severity, start_time, end_time,
                description).
        """
        alert_data = self.alerts.get(location)
        if not alert_data:
            return {"location": location, "alerts": []}
        return deepcopy(alert_data)

    # ---- Historical Weather ----

    def get_historical_weather(self, location: str, date: str) -> Dict[str, Any]:
        """
        Get historical weather for a past date (simplified).

        Args:
            location (str): Location name or identifier.
            date (str): Date in ISO format (YYYY-MM-DD).

        Returns:
            Dict[str, Any]: location, date, condition, temp_high, temp_low,
                precipitation.
        """
        loc_data = self.historical_weather.get(location)
        if not loc_data:
            raise YahooWeatherError(
                "LOCATION_NOT_FOUND", f"No historical data for location '{location}'."
            )
        day_data = loc_data.get(date)
        if not day_data:
            raise YahooWeatherError(
                "DATE_NOT_FOUND", f"No historical data for date '{date}'."
            )
        return deepcopy(day_data)

    # ---- Astronomy (Yahoo-specific) ----

    def get_astronomy(self, location: str) -> Dict[str, Any]:
        """
        Get astronomy data: sunrise, sunset, moon phase from the daily
        forecast data.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location, sunrise, sunset (from today's forecast
                if available).
        """
        forecast = self.daily_forecast.get(location)
        if not forecast:
            raise YahooWeatherError(
                "LOCATION_NOT_FOUND", f"No forecast data for location '{location}'."
            )
        days = forecast.get("days", [])
        today = days[0] if days else {}
        return {
            "location": location,
            "sunrise": today.get("sunrise"),
            "sunset": today.get("sunset"),
        }

    # ---- Pressure Trend (Yahoo-specific) ----

    def get_pressure_trend(self, location: str) -> Dict[str, Any]:
        """
        Get barometric pressure with trend analysis from current conditions.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location, current_pressure, trend,
                trend_description, forecast_implication.
        """
        cw = self._require_current_weather(location)
        # Derive pressure from wind speed heuristic
        wind = cw.get("wind", {})
        speed = wind.get("speed", 0)
        if speed > 20:
            trend = "falling"
        elif speed < 5:
            trend = "rising"
        else:
            trend = "steady"
        implications = {
            "rising": "Improving conditions expected. Clearing skies likely.",
            "falling": "Deteriorating conditions possible. Precipitation may develop.",
            "steady": "Conditions expected to remain similar.",
        }
        return {
            "location": location,
            "trend": trend,
            "trend_description": f"Pressure is {trend}.",
            "forecast_implication": implications.get(trend, ""),
        }

    # ---- Wind Details (Yahoo-specific) ----

    def get_wind_details(self, location: str) -> Dict[str, Any]:
        """
        Get detailed wind information with Beaufort scale.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location, speed, direction, gust,
                beaufort_scale, beaufort_description.
        """
        cw = self._require_current_weather(location)
        wind = cw.get("wind", {})
        speed = wind.get("speed", 0)
        direction = wind.get("direction", "N")
        gust = round(speed * 1.4, 1)
        # Beaufort scale (simplified)
        if speed < 1:
            bf, desc = 0, "Calm"
        elif speed < 8:
            bf, desc = 2, "Light breeze"
        elif speed < 19:
            bf, desc = 4, "Moderate breeze"
        elif speed < 32:
            bf, desc = 6, "Strong breeze"
        elif speed < 47:
            bf, desc = 8, "Gale"
        elif speed < 64:
            bf, desc = 10, "Storm"
        else:
            bf, desc = 12, "Hurricane force"
        return {
            "location": location,
            "speed": speed,
            "direction": direction,
            "gust": gust,
            "beaufort_scale": bf,
            "beaufort_description": desc,
        }

    # ---- Comparison (simpler than weather.com) ----

    def compare_locations(self, locations: List[str]) -> List[Dict[str, Any]]:
        """
        Compare current weather across locations (max 3).

        Args:
            locations (List[str]): Location names (max 3).

        Returns:
            List[Dict[str, Any]]: Current conditions for each location
                with location, temperature, condition, humidity, wind.
        """
        if len(locations) > 3:
            raise YahooWeatherError(
                "TOO_MANY_LOCATIONS",
                "Maximum 3 locations for comparison.",
                suggested_action="Use Weather.com for comparing up to 5 locations.",
            )
        results = []
        for loc in locations:
            cw = self.current_weather.get(loc, {})
            results.append(
                {
                    "location": loc,
                    "temperature": cw.get("temperature"),
                    "condition": cw.get("condition"),
                    "humidity": cw.get("humidity"),
                    "wind": cw.get("wind"),
                }
            )
        return results

    # ---- Temperature Conversion ----

    def convert_temperature(self, value: float, from_unit: str) -> Dict[str, Any]:
        """
        Convert temperature between Fahrenheit and Celsius.

        Args:
            value (float): Temperature value.
            from_unit (str): Source unit — "F" or "C".

        Returns:
            Dict[str, Any]: original, converted, from_unit, to_unit.
        """
        if from_unit.upper() == "F":
            converted = round((value - 32) * 5 / 9, 1)
            to_unit = "C"
        elif from_unit.upper() == "C":
            converted = round(value * 9 / 5 + 32, 1)
            to_unit = "F"
        else:
            raise YahooWeatherError("INVALID_UNIT", "Unit must be 'F' or 'C'.")
        return {
            "original": value,
            "from_unit": from_unit.upper(),
            "converted": converted,
            "to_unit": to_unit,
        }
