"""
Uber Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Ride types with surge pricing multiplier, scheduled rides, fare splitting,
  multi-stop rides, driver matching, tipping, and ride rating.
"""

from __future__ import annotations

import copy
import math
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base_service import BaseServiceAPI


class UberError(Exception):
    def __init__(self, error_code: str, message: str,
                 suggested_action: str = "", context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error = {"error_code": error_code, "message": message,
                      "suggested_action": suggested_action, "context": context or {}}

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self.error)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _haversine_miles(lat1, lng1, lat2, lng2) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1); dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


DEFAULT_STATE = {
    "random_seed": 8003,
    "profile": {},
    "rides": {},
    "drivers": {},
    "ride_types": {},
    "offers": {},
}


class UberAPI(BaseServiceAPI):
    """
    In-memory dummy Uber ride-hailing platform.

    State variables:
    - profile: {name, email, phone, saved_places[], payment_method[],
      promo[offer_id]}
    - rides: Dict of {ride_id -> {ride_id, pickup{lat, lng}, dropoff{lat, lng},
      ride_type, status, fare_total, surge_multiplier, driver_id?, eta_pickup_min?,
      eta_dropoff_min?, scheduled_time?, stops[], tip_amount, rating?, created_at}}
    - drivers: Dict of {driver_id -> {driver_id, name, rating, vehicle,
      availability}}
    - ride_types: Dict of {ride_type_id -> {ride_type_id, name, base_fare,
      capacity, available?}}
    - offers: Dict of {offer_id -> {offer_id, discount, min_ride_fare?, used?}}

    Uber model: surge pricing (multiplier-based), scheduled rides, multi-stop
    rides, fare splitting, driver matching, tipping, and ride rating.
    """

    _STATE_KEYS = ("profile", "rides", "drivers", "ride_types", "offers")
    _ID_COUNTER_DEFAULTS = {"ride": 0, "split": 0}
    _DEFAULT_SEED = 8003

    def __init__(self):
        super().__init__()
        self.profile: Dict[str, Any]
        self.rides: Dict[str, Dict[str, Any]]
        self.drivers: Dict[str, Dict[str, Any]]
        self.ride_types: Dict[str, Dict[str, Any]]
        self.offers: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Uber ride-hailing API, which provides "
            "ride requests with surge pricing, price estimates, scheduled rides, "
            "multi-stop rides, fare splitting, driver info, and ride history."
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
        self._random = random.Random(
            scenario.get("random_seed", DEFAULT_STATE_COPY["random_seed"])
        )
        self.profile = scenario.get("profile", DEFAULT_STATE_COPY["profile"])
        self.rides = scenario.get("rides", DEFAULT_STATE_COPY["rides"])
        self.drivers = scenario.get("drivers", DEFAULT_STATE_COPY["drivers"])
        self.ride_types = scenario.get("ride_types", DEFAULT_STATE_COPY["ride_types"])
        self.offers = scenario.get("offers", DEFAULT_STATE_COPY["offers"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, UberAPI):
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

    def _require_ride(self, rid: str):
        r = self.rides.get(rid)
        if not r: raise UberError("RIDE_NOT_FOUND", f"Ride '{rid}' not found.")
        return r

    def _require_ride_type(self, rtid: str):
        rt = self.ride_types.get(rtid)
        if not rt: raise UberError("INVALID_RIDE_TYPE", f"Ride type '{rtid}' not found.")
        return rt

    def _find_available_driver(self, ride_type_id: str):
        """Find the first available driver."""
        for d in self.drivers.values():
            if d.get("availability") == "available":
                return d
        return None

    def _compute_fare(self, distance: float, duration_min: float,
                      ride_type: Dict[str, Any], surge: float) -> float:
        base = ride_type.get("base_fare", 5.0)
        per_mile = 1.50  # standard rate
        per_minute = 0.25
        fare = base + per_mile * distance + per_minute * duration_min
        fare *= surge
        return round(max(fare, base), 2)

    def _get_surge_multiplier(self) -> float:
        """Generate a surge multiplier between 1.0 and 2.0."""
        return round(1.0 + self._rng.random() * 1.0, 1)

    # ---- User ----

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get the current user's profile.

        Returns:
            Dict[str, Any]: name, email, phone, saved_places,
                payment_method, promo.
        """
        return deepcopy(self.profile)

    def add_saved_place(
        self, label: str, address: str, lat: float, lng: float,
    ) -> Dict[str, Any]:
        """
        Add a saved place (e.g. Home, Work) to the profile.

        Args:
            label (str): Place label (e.g. "Home", "Work").
            address (str): Street address.
            lat (float): Latitude.
            lng (float): Longitude.

        Returns:
            Dict[str, Any]: label, address, status "added".
        """
        place = {"label": label, "address": address, "lat": lat, "lng": lng}
        self.profile.setdefault("saved_places", []).append(place)
        return {"label": label, "address": address, "status": "added"}

    def remove_saved_place(self, label: str) -> Dict[str, Any]:
        """
        Remove a saved place by label.

        Args:
            label (str): The label of the place to remove.

        Returns:
            Dict[str, Any]: label, status "removed".
        """
        places = self.profile.get("saved_places", [])
        new_list = [p for p in places if p.get("label") != label]
        if len(new_list) == len(places):
            raise UberError("PLACE_NOT_FOUND", f"Saved place '{label}' not found.")
        self.profile["saved_places"] = new_list
        return {"label": label, "status": "removed"}

    # ---- Ride Types & Estimates ----

    def list_ride_types(self) -> List[Dict[str, Any]]:
        """
        List all available ride types with base fares and capacity.

        Returns:
            List[Dict[str, Any]]: Ride type objects.
        """
        return [deepcopy(rt) for rt in self.ride_types.values()
                if rt.get("available", True)]

    def estimate_ride(
        self, pickup_lat: float, pickup_lng: float,
        dropoff_lat: float, dropoff_lng: float,
        ride_type_id: str,
    ) -> Dict[str, Any]:
        """
        Get a price/time estimate for a single ride type.

        Args:
            pickup_lat (float): Pickup latitude.
            pickup_lng (float): Pickup longitude.
            dropoff_lat (float): Dropoff latitude.
            dropoff_lng (float): Dropoff longitude.
            ride_type_id (str): The ride type.

        Returns:
            Dict[str, Any]: ride_type_id, estimated_fare, distance_miles,
                duration_minutes, surge_multiplier, eta_pickup_min.
        """
        rt = self._require_ride_type(ride_type_id)
        dist = _haversine_miles(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        duration = max(5, dist * 3)
        surge = self._get_surge_multiplier()
        price = self._compute_fare(dist, duration, rt, surge)
        eta = self._rng.randint(3, 15)
        return {
            "ride_type_id": ride_type_id,
            "estimated_fare": price,
            "distance_miles": round(dist, 1),
            "duration_minutes": round(duration),
            "surge_multiplier": surge,
            "eta_pickup_min": eta,
        }

    def get_price_estimates(
        self, pickup_lat: float, pickup_lng: float,
        dropoff_lat: float, dropoff_lng: float,
    ) -> List[Dict[str, Any]]:
        """
        Get price estimates for all available ride types.

        Args:
            pickup_lat (float): Pickup latitude.
            pickup_lng (float): Pickup longitude.
            dropoff_lat (float): Dropoff latitude.
            dropoff_lng (float): Dropoff longitude.

        Returns:
            List[Dict[str, Any]]: Estimates for each ride type.
        """
        results = []
        for rt_id in self.ride_types:
            rt = self.ride_types[rt_id]
            if not rt.get("available", True):
                continue
            est = self.estimate_ride(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng, rt_id)
            results.append(est)
        return results

    # ---- Rides ----

    def request_ride(
        self, pickup_lat: float, pickup_lng: float,
        dropoff_lat: float, dropoff_lng: float,
        ride_type_id: str,
        scheduled_time: Optional[str] = None,
        stops: Optional[List[Dict[str, Any]]] = None,
        payment_method_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Request a ride. Supports scheduled rides and multi-stop rides.

        Args:
            pickup_lat (float): Pickup latitude.
            pickup_lng (float): Pickup longitude.
            dropoff_lat (float): Dropoff latitude.
            dropoff_lng (float): Dropoff longitude.
            ride_type_id (str): The ride type.
            scheduled_time (str, optional): ISO-8601 time for scheduled rides.
            stops (List[Dict], optional): Intermediate stops, each with
                lat (float), lng (float).
            payment_method_id (str, optional): Payment method from profile.

        Returns:
            Dict[str, Any]: ride_id, status, fare_total, surge_multiplier,
                driver info (if matched), eta_pickup_min.
        """
        rt = self._require_ride_type(ride_type_id)
        if not rt.get("available", True):
            raise UberError("RIDE_TYPE_UNAVAILABLE", f"Ride type '{ride_type_id}' is not available.")

        dist = _haversine_miles(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        duration = max(5, dist * 3)
        surge = self._get_surge_multiplier()
        fare = self._compute_fare(dist, duration, rt, surge)

        driver = self._find_available_driver(ride_type_id)
        if scheduled_time:
            status = "scheduled"
        elif driver:
            status = "matched"
            driver["availability"] = "on_trip"
        else:
            status = "requesting"

        eta_pickup = self._rng.randint(3, 12) if driver else None
        eta_dropoff = round(duration) if driver else None

        now = _utc_now_iso()
        ride_id = self._new_id("ride")
        self.rides[ride_id] = {
            "ride_id": ride_id,
            "pickup": {"lat": pickup_lat, "lng": pickup_lng},
            "dropoff": {"lat": dropoff_lat, "lng": dropoff_lng},
            "stops": stops or [],
            "ride_type": ride_type_id,
            "status": status,
            "fare_total": fare,
            "surge_multiplier": surge,
            "driver_id": driver["driver_id"] if driver else None,
            "eta_pickup_min": eta_pickup,
            "eta_dropoff_min": eta_dropoff,
            "scheduled_time": scheduled_time,
            "tip_amount": 0,
            "rating": None,
            "created_at": now,
        }

        result = {
            "ride_id": ride_id, "status": status, "fare_total": fare,
            "surge_multiplier": surge, "eta_pickup_min": eta_pickup,
        }
        if driver:
            result["driver"] = {
                "name": driver.get("name"),
                "rating": driver.get("rating"),
                "vehicle": driver.get("vehicle"),
            }
        return result

    def cancel_ride(self, ride_id: str) -> Dict[str, Any]:
        """
        Cancel a ride. May incur a cancellation fee if driver is en route.

        Args:
            ride_id (str): The ride to cancel.

        Returns:
            Dict[str, Any]: ride_id, status "cancelled", cancellation_fee.
        """
        ride = self._require_ride(ride_id)
        if ride.get("status") in ("completed", "cancelled"):
            raise UberError("CANNOT_CANCEL", f"Ride is already {ride.get('status')}.")
        cancel_fee = 5.0 if ride.get("status") in ("driver_en_route", "arrived") else 0
        if ride.get("driver_id"):
            d = self.drivers.get(ride["driver_id"])
            if d:
                d["availability"] = "available"
        ride["status"] = "cancelled"
        return {"ride_id": ride_id, "status": "cancelled", "cancellation_fee": cancel_fee}

    def get_ride(self, ride_id: str) -> Dict[str, Any]:
        """
        Get full ride details.

        Args:
            ride_id (str): The ride.

        Returns:
            Dict[str, Any]: Full ride object.
        """
        return deepcopy(self._require_ride(ride_id))

    def list_rides(self, status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        List ride history, optionally filtered by status.

        Args:
            status (str, optional): Filter by ride status.
            limit (int): Maximum results. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Rides sorted newest first.
        """
        results = []
        for r in self.rides.values():
            if status and r.get("status") != status:
                continue
            results.append(deepcopy(r))
        results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return results[:limit]

    def rate_ride(self, ride_id: str, rating: int) -> Dict[str, Any]:
        """
        Rate a completed ride (1-5 stars).

        Args:
            ride_id (str): The ride to rate.
            rating (int): Rating from 1 to 5.

        Returns:
            Dict[str, Any]: ride_id, rating, status "rated".
        """
        ride = self._require_ride(ride_id)
        if ride.get("status") != "completed":
            raise UberError("RIDE_NOT_COMPLETED", "Can only rate completed rides.")
        if rating < 1 or rating > 5:
            raise UberError("INVALID_RATING", "Rating must be 1-5.")
        ride["rating"] = rating
        return {"ride_id": ride_id, "rating": rating, "status": "rated"}

    def tip_driver(self, ride_id: str, amount: float) -> Dict[str, Any]:
        """
        Add a tip to a completed ride.

        Args:
            ride_id (str): The ride.
            amount (float): Tip amount (must be > 0).

        Returns:
            Dict[str, Any]: ride_id, tip_amount.
        """
        ride = self._require_ride(ride_id)
        if ride.get("status") != "completed":
            raise UberError("RIDE_NOT_COMPLETED", "Can only tip on completed rides.")
        if amount <= 0:
            raise UberError("INVALID_AMOUNT", "Tip must be positive.")
        ride["tip_amount"] = round(ride.get("tip_amount", 0) + amount, 2)
        return {"ride_id": ride_id, "tip_amount": ride["tip_amount"]}

    # ---- Fare Splitting (Uber-specific) ----

    def split_fare(self, ride_id: str, num_splits: int) -> Dict[str, Any]:
        """
        Split the fare of a ride evenly among multiple people.

        Args:
            ride_id (str): The ride to split.
            num_splits (int): Total number of people sharing (including you).

        Returns:
            Dict[str, Any]: ride_id, num_splits, amount_per_person.
        """
        ride = self._require_ride(ride_id)
        if num_splits < 2:
            raise UberError("INVALID_SPLIT", "Must split between at least 2 people.")
        total = ride.get("fare_total", 0)
        per_person = round(total / num_splits, 2)
        return {"ride_id": ride_id, "num_splits": num_splits, "amount_per_person": per_person}

    # ---- Driver ----

    def get_driver_info(self, ride_id: str) -> Dict[str, Any]:
        """
        Get driver details for a ride.

        Args:
            ride_id (str): The ride.

        Returns:
            Dict[str, Any]: Driver object with name, rating, vehicle,
                availability.
        """
        ride = self._require_ride(ride_id)
        did = ride.get("driver_id")
        if not did:
            raise UberError("NO_DRIVER", "No driver assigned to this ride yet.")
        driver = self.drivers.get(did)
        if not driver:
            raise UberError("DRIVER_NOT_FOUND", "Driver information unavailable.")
        return deepcopy(driver)

    # ---- Offers ----

    def apply_offer(self, offer_id: str) -> Dict[str, Any]:
        """
        Apply a promotional offer to the user's account.

        Args:
            offer_id (str): The offer to apply.

        Returns:
            Dict[str, Any]: offer_id, discount, status "applied".
        """
        offer = self.offers.get(offer_id)
        if not offer:
            raise UberError("OFFER_NOT_FOUND", f"Offer '{offer_id}' not found.")
        if offer.get("used"):
            raise UberError("OFFER_USED", "This offer has already been used.")
        offer["used"] = True
        promos = self.profile.get("promo", [])
        if offer_id not in promos:
            self.profile.setdefault("promo", []).append(offer_id)
        return {
            "offer_id": offer_id,
            "discount": offer.get("discount"),
            "status": "applied",
        }

    def list_offers(self) -> List[Dict[str, Any]]:
        """
        List available promotional offers.

        Returns:
            List[Dict[str, Any]]: Offer objects that have not been used.
        """
        return [deepcopy(o) for o in self.offers.values() if not o.get("used")]
