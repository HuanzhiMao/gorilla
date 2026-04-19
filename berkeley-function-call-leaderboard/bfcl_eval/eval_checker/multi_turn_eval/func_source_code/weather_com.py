"""
Weather.com (The Weather Channel) Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Comprehensive weather platform: current conditions, hourly (48h), 10-day forecast.
- Air Quality Index (AQI), UV index, severe weather alerts.
- Location comparison, precipitation radar, saved locations.
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .server_patch_mixin import PatchableMixin


class WeatherComError(Exception):
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
    "random_seed": 9001,
    "profile": {},
    "current_weather": {},
    "hourly_forecast": {},
    "daily_forecast": {},
    "alerts": {},
    "air_quality": {},
    "historical_weather": {},
    "location_index": {},
    "air_quality_forecast": {},
    "activity_forecasts": {},
    "pollen_data": {},
}


class WeatherComAPI(PatchableMixin):
    """
    In-memory dummy Weather.com — comprehensive weather platform.

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
    - air_quality: Dict of {location -> {location, aqi, category, pm25,
      pm10, ozone, no2, health_advice}}
    - historical_weather: Dict of {location -> {date -> {location, date,
      condition, temp_high, temp_low, precipitation, humidity,
      wind{speed, direction}}}}
    - location_index: Dict of {location_name -> {location_id, name,
      numeric_index?, state, country, lat, lon}}

    Weather.com model: comprehensive weather with current conditions,
    48-hour hourly forecasts, 10-day daily forecasts, AQI, UV index,
    severe weather alerts, precipitation radar, location comparison,
    air quality monitoring, historical weather data, and location resolution.

    Methods include: get_current_weather, get_uv_index, get_precipitation_radar,
    get_hourly_forecast, get_daily_forecast, get_alerts, get_alert_details,
    compare_locations, search_location, get_location, get_air_quality,
    get_historical_weather.
    """


    def __init__(self):
        self._id_counters = {}
        self.profile: Dict[str, Any]
        self.current_weather: Dict[str, Dict[str, Any]]
        self.hourly_forecast: Dict[str, Dict[str, Any]]
        self.daily_forecast: Dict[str, Dict[str, Any]]
        self.alerts: Dict[str, Dict[str, Any]]
        self.air_quality: Dict[str, Dict[str, Any]]
        self.historical_weather: Dict[str, Dict[str, Dict[str, Any]]]
        self.location_index: Dict[str, Dict[str, Any]]
        self.air_quality_forecast: Dict[str, Dict[str, Any]]
        self.activity_forecasts: Dict[str, Dict[str, Any]]
        self.pollen_data: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Weather.com API, which provides "
            "current conditions, hourly (48h) and 10-day forecasts, "
            "UV index, severe weather alerts, precipitation radar, "
            "location comparison, Air Quality Index (AQI), historical "
            "weather data, and location resolution."
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
        self.air_quality = scenario.get(
            "air_quality", DEFAULT_STATE_COPY["air_quality"]
        )
        self.historical_weather = scenario.get(
            "historical_weather", DEFAULT_STATE_COPY["historical_weather"]
        )
        self.location_index = scenario.get(
            "location_index", DEFAULT_STATE_COPY["location_index"]
        )
        self.air_quality_forecast = scenario.get(
            "air_quality_forecast", DEFAULT_STATE_COPY["air_quality_forecast"]
        )
        self.activity_forecasts = scenario.get(
            "activity_forecasts", DEFAULT_STATE_COPY["activity_forecasts"]
        )
        self.pollen_data = scenario.get(
            "pollen_data", DEFAULT_STATE_COPY["pollen_data"]
        )
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, WeatherComAPI):
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
            raise WeatherComError(
                "LOCATION_NOT_FOUND",
                f"No weather data for location '{location}'.",
                suggested_action="Check the location name or use a different location.",
            )
        return cw

    # ---- Location Resolution ----

    def search_location(self, query: str) -> Dict[str, Any]:
        """
        Search for a location by name and return its metadata.

        Args:
            query (str): Location name or partial match (e.g. "Portland", "Portland, OR").

        Returns:
            Dict[str, Any]: location_id, name, state, country, lat, lon.
        """
        for loc_name, meta in self.location_index.items():
            if _matches_query(loc_name, query):
                return deepcopy(meta)
        raise WeatherComError(
            "LOCATION_NOT_FOUND",
            f"No location matching '{query}'.",
            suggested_action="Check spelling or try a more specific query.",
        )

    def get_location(self, location_name: str) -> Dict[str, Any]:
        """
        Get location metadata including numeric index.

        Args:
            location_name (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location_id, name, numeric_index, state, country, lat, lon.
        """
        meta = self.location_index.get(location_name)
        if not meta:
            raise WeatherComError(
                "LOCATION_NOT_FOUND", f"No location metadata for '{location_name}'."
            )
        return deepcopy(meta)

    # ---- Profile ----

    def get_weather_preferences(self) -> Dict[str, Any]:
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
                raise WeatherComError(
                    "LABEL_EXISTS",
                    f"Saved location with label '{label}' already exists.",
                    suggested_action="Use a different label or remove the existing one.",
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
            raise WeatherComError(
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

    # ---- Current Conditions ----

    def get_current_weather(self, location: str) -> Dict[str, Any]:
        """
        Get current weather conditions for a location.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location, observed_at, condition, temperature,
                feels_like, humidity, wind{speed, direction}, precipitation,
                visibility, uv_index.
        """
        return deepcopy(self._require_current_weather(location))

    def get_uv_index(self, location: str) -> Dict[str, Any]:
        """
        Get current UV index with safety recommendations.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location, uv_index, category, safe_exposure_minutes,
                recommendations.
        """
        cw = self._require_current_weather(location)
        uv = cw.get("uv_index", 0)
        if uv <= 2:
            cat, safe_min = "low", 60
        elif uv <= 5:
            cat, safe_min = "moderate", 45
        elif uv <= 7:
            cat, safe_min = "high", 30
        elif uv <= 10:
            cat, safe_min = "very_high", 15
        else:
            cat, safe_min = "extreme", 10
        recs = {
            "low": "Minimal protection needed.",
            "moderate": "Wear sunscreen SPF 30+.",
            "high": "Wear sunscreen, hat, and sunglasses. Seek shade during midday.",
            "very_high": "Avoid sun exposure 10am-4pm. SPF 50+ recommended.",
            "extreme": "Stay indoors during peak hours. Full sun protection essential.",
        }
        return {
            "location": location,
            "uv_index": uv,
            "category": cat,
            "safe_exposure_minutes": safe_min,
            "recommendations": recs[cat],
        }

    def get_precipitation_radar(self, location: str) -> Dict[str, Any]:
        """
        Get a simulated precipitation radar snapshot.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location, timestamp, radar_intensity (0-5),
                coverage_pct, description.
        """
        cw = self._require_current_weather(location)
        intensity = 0
        condition = cw.get("condition", "clear").lower()
        if "rain" in condition or "shower" in condition:
            intensity = self._rng.randint(2, 4)
        elif "storm" in condition or "thunder" in condition:
            intensity = self._rng.randint(3, 5)
        elif "drizzle" in condition:
            intensity = 1
        elif "snow" in condition:
            intensity = self._rng.randint(1, 3)
        coverage = min(100, intensity * self._rng.randint(10, 25))
        return {
            "location": location,
            "timestamp": _utc_now_iso(),
            "radar_intensity": intensity,
            "coverage_pct": coverage,
            "description": f"{'No' if intensity == 0 else 'Active'} precipitation detected.",
        }

    # ---- Air Quality (Weather.com exclusive) ----

    def get_air_quality(self, location: str) -> Dict[str, Any]:
        """
        Get current Air Quality Index and pollutant levels.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location, aqi, category, pm25, pm10, ozone, no2,
                health_advice.
        """
        aq = self.air_quality.get(location)
        if not aq:
            raise WeatherComError(
                "LOCATION_NOT_FOUND",
                f"No air quality data for location '{location}'.",
                suggested_action="Check the location name.",
            )
        return deepcopy(aq)

    # ---- Hourly Forecast ----

    def get_hourly_forecast(self, location: str, hours: int = 48) -> Dict[str, Any]:
        """
        Get hourly forecast up to 48 hours.

        Args:
            location (str): Location name or identifier.
            hours (int): Number of hours (1-48). Defaults to 48.

        Returns:
            Dict[str, Any]: location, hours (list of hourly forecasts, each
                with time, condition, temperature, feels_like,
                precipitation_chance, precipitation_amount, wind{speed, direction}).
        """
        if hours < 1 or hours > 48:
            raise WeatherComError("INVALID_HOURS", "Hours must be between 1 and 48.")
        forecast = self.hourly_forecast.get(location)
        if not forecast:
            raise WeatherComError(
                "LOCATION_NOT_FOUND", f"No hourly forecast for location '{location}'."
            )
        result = deepcopy(forecast)
        result["hours"] = result.get("hours", [])[:hours]
        return result

    # ---- Daily Forecast ----

    def get_daily_forecast(self, location: str, days: int = 10) -> Dict[str, Any]:
        """
        Get daily forecast up to 10 days.

        Args:
            location (str): Location name or identifier.
            days (int): Number of days (1-10). Defaults to 10.

        Returns:
            Dict[str, Any]: location, days (list of daily forecasts, each
                with date, condition_day, condition_night, temp_min, temp_max,
                precipitation_chance, precipitation_amount, sunrise, sunset).
        """
        if days < 1 or days > 10:
            raise WeatherComError("INVALID_DAYS", "Days must be between 1 and 10.")
        forecast = self.daily_forecast.get(location)
        if not forecast:
            raise WeatherComError(
                "LOCATION_NOT_FOUND", f"No daily forecast for location '{location}'."
            )
        result = deepcopy(forecast)
        result["days"] = result.get("days", [])[:days]
        return result

    # ---- Alerts ----

    def get_alerts(self, location: str) -> Dict[str, Any]:
        """
        Get active severe weather alerts for a location.

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

    def get_alert_details(self, location: str, alert_id: str) -> Dict[str, Any]:
        """
        Get full details for a specific alert.

        Args:
            location (str): Location name or identifier.
            alert_id (str): The alert identifier.

        Returns:
            Dict[str, Any]: Full alert object with event, severity,
                start_time, end_time, description.
        """
        alert_data = self.alerts.get(location, {})
        for alert in alert_data.get("alerts", []):
            if alert.get("alert_id") == alert_id:
                return deepcopy(alert)
        raise WeatherComError("ALERT_NOT_FOUND", f"Alert '{alert_id}' not found.")

    # ---- Historical Weather ----

    def get_historical_weather(self, location: str, date: str) -> Dict[str, Any]:
        """
        Get historical weather conditions for a past date.

        Args:
            location (str): Location name or identifier.
            date (str): Date in ISO format (YYYY-MM-DD).

        Returns:
            Dict[str, Any]: location, date, condition, temp_high, temp_low,
                precipitation, humidity, wind{speed, direction}.
        """
        loc_data = self.historical_weather.get(location)
        if not loc_data:
            raise WeatherComError(
                "LOCATION_NOT_FOUND", f"No historical data for location '{location}'."
            )
        day_data = loc_data.get(date)
        if not day_data:
            raise WeatherComError(
                "DATE_NOT_FOUND",
                f"No historical data for date '{date}'.",
                suggested_action="Historical data available for the last 365 days.",
            )
        return deepcopy(day_data)

    # ---- Comparison ----

    def compare_locations(self, locations: List[str]) -> List[Dict[str, Any]]:
        """
        Compare current weather across multiple locations.

        Args:
            locations (List[str]): Location names (max 5).

        Returns:
            List[Dict[str, Any]]: Current conditions for each location
                with location, temperature, feels_like, humidity, condition,
                wind, uv_index.
        """
        if len(locations) > 5:
            raise WeatherComError(
                "TOO_MANY_LOCATIONS", "Maximum 5 locations for comparison."
            )
        results = []
        for loc in locations:
            cw = self.current_weather.get(loc, {})
            results.append(
                {
                    "location": loc,
                    "temperature": cw.get("temperature"),
                    "feels_like": cw.get("feels_like"),
                    "humidity": cw.get("humidity"),
                    "condition": cw.get("condition"),
                    "wind": cw.get("wind"),
                    "uv_index": cw.get("uv_index"),
                }
            )
        return results

    # ---- Air Quality Forecast ----

    def get_air_quality_forecast(
        self, location: str, hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get hourly Air Quality Index forecast.

        Args:
            location (str): Location name or identifier.
            hours (int): Number of forecast hours (1-72). Defaults to 24.

        Returns:
            Dict[str, Any]: location, hours (list of hourly AQI forecasts,
                each with time, aqi, category, primary_pollutant).
        """
        if hours < 1 or hours > 72:
            raise WeatherComError(
                "INVALID_HOURS", "Hours must be between 1 and 72."
            )
        forecast = self.air_quality_forecast.get(location)
        if not forecast:
            raise WeatherComError(
                "LOCATION_NOT_FOUND",
                f"No air quality forecast for location '{location}'.",
                suggested_action="Check the location name.",
            )
        result = deepcopy(forecast)
        result["hours"] = result.get("hours", [])[:hours]
        return result

    # ---- Outdoor Activity / Lifestyle Index ----

    def get_activity_forecast(
        self, location: str, activity: str
    ) -> Dict[str, Any]:
        """
        Get suitability score and conditions for an outdoor activity based
        on current weather data.

        Args:
            location (str): Location name or identifier.
            activity (str): Activity type — one of "running", "cycling",
                "golf", "bbq", "fishing", "skiing", "hiking", "stargazing".

        Returns:
            Dict[str, Any]: location, activity, score (1-10),
                description, conditions{temperature, wind_speed,
                precipitation_chance, humidity, uv_index}.
        """
        valid_activities = [
            "running", "cycling", "golf", "bbq",
            "fishing", "skiing", "hiking", "stargazing",
        ]
        if activity not in valid_activities:
            raise WeatherComError(
                "INVALID_ACTIVITY",
                f"Activity '{activity}' is not supported. "
                f"Choose from: {', '.join(valid_activities)}.",
                suggested_action="Use one of the supported activity types.",
            )
        cw = self._require_current_weather(location)
        temp = cw.get("temperature", 70)
        wind_speed = cw.get("wind", {}).get("speed", 0)
        humidity = cw.get("humidity", 50)
        uv = cw.get("uv_index", 0)
        precip = cw.get("precipitation", 0)
        condition = cw.get("condition", "").lower()

        # Base score starts at 7 and is adjusted per activity
        score = 7.0

        if activity == "running":
            if temp < 30 or temp > 95:
                score -= 3
            elif temp < 45 or temp > 85:
                score -= 1
            if wind_speed > 20:
                score -= 2
            if precip > 0:
                score -= 2
            if humidity > 80:
                score -= 1
        elif activity == "cycling":
            if wind_speed > 25:
                score -= 3
            elif wind_speed > 15:
                score -= 1
            if precip > 0:
                score -= 3
            if temp < 35 or temp > 95:
                score -= 2
        elif activity == "golf":
            if precip > 0:
                score -= 3
            if wind_speed > 20:
                score -= 2
            if temp < 45 or temp > 95:
                score -= 2
        elif activity == "bbq":
            if "rain" in condition or "storm" in condition:
                score -= 4
            if precip > 0:
                score -= 2
            if temp < 50:
                score -= 1
        elif activity == "fishing":
            if "storm" in condition or "thunder" in condition:
                score -= 4
            if wind_speed > 25:
                score -= 2
            if precip > 0.5:
                score -= 1
        elif activity == "skiing":
            if temp > 40:
                score -= 3
            elif temp > 32:
                score -= 1
            if "snow" in condition:
                score += 2
            if wind_speed > 30:
                score -= 2
        elif activity == "hiking":
            if precip > 0:
                score -= 2
            if temp < 30 or temp > 95:
                score -= 2
            if uv > 8:
                score -= 1
            if wind_speed > 25:
                score -= 1
        elif activity == "stargazing":
            if "cloud" in condition or "overcast" in condition:
                score -= 3
            if "rain" in condition or "storm" in condition:
                score -= 4
            if humidity > 80:
                score -= 1
            if wind_speed < 10:
                score += 1

        score = max(1, min(10, round(score)))

        descriptions = {
            10: "Perfect conditions.",
            9: "Excellent conditions.",
            8: "Very good conditions.",
            7: "Good conditions.",
            6: "Fair conditions.",
            5: "Marginal conditions.",
            4: "Below average conditions.",
            3: "Poor conditions.",
            2: "Very poor conditions.",
            1: "Not recommended.",
        }

        return {
            "location": location,
            "activity": activity,
            "score": score,
            "description": descriptions.get(score, "Unknown conditions."),
            "conditions": {
                "temperature": temp,
                "wind_speed": wind_speed,
                "precipitation_chance": cw.get("precipitation", 0),
                "humidity": humidity,
                "uv_index": uv,
            },
        }

    def get_pollen_count(self, location: str) -> Dict[str, Any]:
        """
        Get pollen counts by type and overall allergy risk level.

        Args:
            location (str): Location name or identifier.

        Returns:
            Dict[str, Any]: location, tree_pollen, grass_pollen,
                ragweed_pollen, overall_risk.
        """
        pollen = self.pollen_data.get(location)
        if not pollen:
            raise WeatherComError(
                "LOCATION_NOT_FOUND",
                f"No pollen data for location '{location}'.",
                suggested_action="Check the location name.",
            )
        return deepcopy(pollen)
