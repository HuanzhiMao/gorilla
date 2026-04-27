"""
Lyft Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Ride types with Prime Time percentage-based pricing, Wait & Save mode,
  priority pickup, round-up donations, and ride rating.
"""

from __future__ import annotations

import copy
import math
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .server_patch_mixin import PatchableMixin


class LyftError(Exception):
    def __init__(self, error_code: str, message: str,
                 suggested_action: str = "", context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error = {"error_code": error_code, "message": message,
                      "suggested_action": suggested_action, "context": context or {}}

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self.error)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


DEFAULT_STATE = {
    "random_seed": 8004,
    "profile": {},
    "rides": {},
    "drivers": {},
    "ride_types": {},
    "offers": {},
    "scheduled_rides": {},
    "wait_and_save": {},
    "ride_challenges": [],
    "ride_streak": {},
}


class LyftAPI(PatchableMixin):
    """
    In-memory dummy Lyft ride-hailing platform.

    State variables:
    - profile: {name, email, phone, saved_places[], payment_method[],
      promo[offer_id], round_up_enabled?}
    - rides: Dict of {ride_id -> {ride_id, pickup{lat, lng}, dropoff{lat, lng},
      ride_type, status, fare_total, prime_time_pct, driver_id?, eta_pickup_min?,
      eta_dropoff_min?, wait_and_save, priority_pickup, tip_amount, rating?,
      round_up_donation, created_at}}
    - drivers: Dict of {driver_id -> {driver_id, name, rating, vehicle,
      availability}}
    - ride_types: Dict of {ride_type_id -> {ride_type_id, name, base_fare,
      capacity, available?}}
    - offers: Dict of {offer_id -> {offer_id, discount, min_ride_fare?, used?}}

    Lyft model: Prime Time percentage-based pricing, Wait & Save mode for
    cheaper fares with longer wait, priority pickup for faster arrival,
    round-up donations, driver matching, tipping, and ride rating.
    """


    def __init__(self):
        self._id_counters = {"ride": 0, "scheduled_ride": 0, "ws_offer": 0}
        self.profile: Dict[str, Any]
        self.rides: Dict[str, Dict[str, Any]]
        self.drivers: Dict[str, Dict[str, Any]]
        self.ride_types: Dict[str, Dict[str, Any]]
        self.offers: Dict[str, Dict[str, Any]]
        self.scheduled_rides: Dict[str, Dict[str, Any]]
        self.wait_and_save: Dict[str, Dict[str, Any]]
        self.ride_challenges: List[Dict[str, Any]]
        self.ride_streak: Dict[str, Any]
        self._api_description = (
            "This tool belongs to the Lyft API, which provides "
            "ride-hailing with Prime Time pricing, Wait & Save, "
            "priority pickup, round-up donations, and ride history."
        )


    def _new_id(self, prefix: str) -> str:
        """Generate the next sequential ID for *prefix* (e.g. ``order_1``)."""
        self._id_counters[prefix] = self._id_counters.get(prefix, 0) + 1
        return f"{prefix}_{self._id_counters[prefix]}"

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
        self.rides = scenario.get("rides", DEFAULT_STATE_COPY["rides"])
        self.drivers = scenario.get("drivers", DEFAULT_STATE_COPY["drivers"])
        self.ride_types = scenario.get("ride_types", DEFAULT_STATE_COPY["ride_types"])
        self.offers = scenario.get("offers", DEFAULT_STATE_COPY["offers"])
        self.scheduled_rides = scenario.get("scheduled_rides", DEFAULT_STATE_COPY["scheduled_rides"])
        self.wait_and_save = scenario.get("wait_and_save", DEFAULT_STATE_COPY["wait_and_save"])
        self.ride_challenges = scenario.get("ride_challenges", deepcopy(DEFAULT_STATE_COPY["ride_challenges"]))
        self.ride_streak = scenario.get("ride_streak", deepcopy(DEFAULT_STATE_COPY["ride_streak"]))
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, LyftAPI):
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
        if not r: raise LyftError("RIDE_NOT_FOUND", f"Ride '{rid}' not found.")
        return r

    def _require_ride_type(self, rtid: str):
        rt = self.ride_types.get(rtid)
        if not rt: raise LyftError("INVALID_RIDE_TYPE", f"Ride type '{rtid}' not found.")
        return rt

    def _find_available_driver(self):
        """Find the first available driver."""
        for d in self.drivers.values():
            if d.get("availability") == "available":
                return d
        return None

    def _get_prime_time_pct(self, lat: float, lon: float) -> int:
        """Prime Time percentage (0, 25, 50, 75, 100) based on location hash."""
        h = abs(hash((round(lat, 2), round(lon, 2)))) % 100
        if h < 60: return 0
        if h < 75: return 25
        if h < 88: return 50
        if h < 95: return 75
        return 100

    def _compute_fare(self, distance: float, duration_min: float,
                      ride_type: Dict[str, Any], prime_time_pct: int,
                      wait_and_save: bool) -> Dict[str, Any]:
        """Compute fare with Prime Time and Wait & Save adjustments."""
        base = ride_type.get("base_fare", 5.0)
        per_mile = 1.15
        per_minute = 0.22
        fare = base + per_mile * distance + per_minute * duration_min
        fare = max(fare, base)

        effective_prime = prime_time_pct
        if wait_and_save:
            effective_prime = 0
            fare = round(fare * 0.80, 2)  # 20% discount for waiting

        prime_amount = round(fare * effective_prime / 100, 2)
        total = round(fare + prime_amount, 2)
        return {
            "base_fare": round(fare, 2),
            "prime_time_pct": effective_prime,
            "prime_time_amount": prime_amount,
            "total_fare": total,
        }

    # ---- User ----

    def get_rider_profile(self) -> Dict[str, Any]:
        """
        Get the current user's profile.

        Returns:
            Dict[str, Any]: name, email, phone, saved_places,
                payment_method, promo.
        """
        return deepcopy(self.profile)

    def save_location(
        self, label: str, address: str, lat: float, lng: float,
    ) -> Dict[str, Any]:
        """
        Add a saved place to the profile.

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

    def delete_location(self, label: str) -> Dict[str, Any]:
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
            raise LyftError("PLACE_NOT_FOUND", f"Saved place '{label}' not found.")
        self.profile["saved_places"] = new_list
        return {"label": label, "status": "removed"}

    # ---- Ride Types & Estimates ----

    def list_ride_modes(self) -> List[Dict[str, Any]]:
        """
        List all available ride types with base fares and capacity.

        Returns:
            List[Dict[str, Any]]: Ride type objects.
        """
        return [deepcopy(rt) for rt in self.ride_types.values()
                if rt.get("available", True)]

    def get_ride_estimates(
        self, pickup_lat: float, pickup_lng: float,
        dropoff_lat: float, dropoff_lng: float,
    ) -> List[Dict[str, Any]]:
        """
        Get fare estimates for all ride types, including Wait & Save prices.

        Args:
            pickup_lat (float): Pickup latitude.
            pickup_lng (float): Pickup longitude.
            dropoff_lat (float): Dropoff latitude.
            dropoff_lng (float): Dropoff longitude.

        Returns:
            List[Dict[str, Any]]: Estimates per ride type with fare,
                prime_time_pct, wait_and_save_fare, eta.
        """
        miles = _haversine_miles(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        minutes = max(5, miles * 2.5 + self._rng.uniform(-2, 3))
        prime_pct = self._get_prime_time_pct(pickup_lat, pickup_lng)

        estimates = []
        for rt_id, rt in self.ride_types.items():
            if not rt.get("available", True):
                continue
            fare_info = self._compute_fare(miles, minutes, rt, prime_pct, False)
            ws_fare_info = self._compute_fare(miles, minutes, rt, prime_pct, True)
            eta = max(2, int(self._rng.uniform(3, 12)))
            estimates.append({
                "ride_type_id": rt_id,
                "estimated_fare": fare_info["total_fare"],
                "distance_miles": round(miles, 1),
                "duration_minutes": round(minutes),
                "prime_time_pct": prime_pct,
                "eta_pickup_min": eta,
                "capacity": rt.get("capacity", 4),
                "wait_and_save_fare": ws_fare_info["total_fare"],
            })
        return estimates

    # ---- Rides ----

    def book_ride(
        self, pickup_lat: float, pickup_lng: float,
        dropoff_lat: float, dropoff_lng: float,
        ride_type_id: str,
        wait_and_save: bool = False,
        priority_pickup: bool = False,
        payment_method_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Request a ride with optional Wait & Save or Priority Pickup.

        Args:
            pickup_lat (float): Pickup latitude.
            pickup_lng (float): Pickup longitude.
            dropoff_lat (float): Dropoff latitude.
            dropoff_lng (float): Dropoff longitude.
            ride_type_id (str): The ride type.
            wait_and_save (bool): Accept longer wait for lower price.
            priority_pickup (bool): Pay extra for faster pickup.
            payment_method_id (str, optional): Payment method from profile.

        Returns:
            Dict[str, Any]: ride_id, status, fare_total, prime_time_pct,
                driver info (if matched), eta_pickup_min, eta_dropoff_min.
        """
        rt = self._require_ride_type(ride_type_id)
        if not rt.get("available", True):
            raise LyftError("RIDE_TYPE_UNAVAILABLE", f"Ride type '{ride_type_id}' is not available.")
        if wait_and_save and priority_pickup:
            raise LyftError("INCOMPATIBLE_OPTIONS",
                             "Cannot use Wait & Save and Priority Pickup together.")

        miles = _haversine_miles(pickup_lat, pickup_lng, dropoff_lat, dropoff_lng)
        minutes = max(5, miles * 2.5 + self._rng.uniform(-2, 3))
        prime_pct = self._get_prime_time_pct(pickup_lat, pickup_lng)

        fare_info = self._compute_fare(miles, minutes, rt, prime_pct, wait_and_save)
        total = fare_info["total_fare"]

        if priority_pickup:
            total = round(total + 3.00, 2)

        driver = self._find_available_driver()
        if driver:
            status = "matched"
            driver["availability"] = "on_trip"
        else:
            status = "requesting"

        eta_pickup = self._rng.randint(3, 10)
        if priority_pickup:
            eta_pickup = max(1, eta_pickup - 3)
        if wait_and_save:
            eta_pickup += self._rng.randint(3, 8)
        eta_dropoff = round(minutes)

        # Round-up donation
        round_up_donation = 0.0
        if self.profile.get("round_up_enabled", False):
            rounded = math.ceil(total)
            round_up_donation = round(rounded - total, 2)

        now = _utc_now_iso()
        ride_id = self._new_id("ride")
        self.rides[ride_id] = {
            "ride_id": ride_id,
            "pickup": {"lat": pickup_lat, "lng": pickup_lng},
            "dropoff": {"lat": dropoff_lat, "lng": dropoff_lng},
            "ride_type": ride_type_id,
            "status": status,
            "fare_total": total,
            "prime_time_pct": fare_info["prime_time_pct"],
            "wait_and_save": wait_and_save,
            "priority_pickup": priority_pickup,
            "driver_id": driver["driver_id"] if driver else None,
            "eta_pickup_min": eta_pickup if driver else None,
            "eta_dropoff_min": eta_dropoff if driver else None,
            "tip_amount": 0,
            "rating": None,
            "round_up_donation": round_up_donation,
            "created_at": now,
        }

        result = {
            "ride_id": ride_id, "status": status, "fare_total": total,
            "prime_time_pct": fare_info["prime_time_pct"],
            "eta_pickup_min": eta_pickup if driver else None,
            "eta_dropoff_min": eta_dropoff if driver else None,
            "wait_and_save": wait_and_save, "priority_pickup": priority_pickup,
        }
        if driver:
            result["driver"] = {
                "name": driver.get("name"),
                "rating": driver.get("rating"),
                "vehicle": driver.get("vehicle"),
            }
        return result

    def cancel_trip(self, ride_id: str) -> Dict[str, Any]:
        """
        Cancel a ride. Fee may apply if driver already en route.

        Args:
            ride_id (str): The ride to cancel.

        Returns:
            Dict[str, Any]: ride_id, status "cancelled", cancel_fee.
        """
        ride = self._require_ride(ride_id)
        if ride.get("status") in ("completed", "cancelled"):
            raise LyftError("CANNOT_CANCEL", f"Ride is already {ride.get('status')}.")
        cancel_fee = 5.0 if ride.get("status") == "en_route_to_pickup" else 0.0
        if ride.get("driver_id"):
            d = self.drivers.get(ride["driver_id"])
            if d:
                d["availability"] = "available"
        ride["status"] = "cancelled"
        return {"ride_id": ride_id, "status": "cancelled", "cancel_fee": cancel_fee}

    def get_trip(self, ride_id: str) -> Dict[str, Any]:
        """
        Get full ride details.

        Args:
            ride_id (str): The ride.

        Returns:
            Dict[str, Any]: Full ride object.
        """
        return deepcopy(self._require_ride(ride_id))

    def list_trip_history(self, status: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
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

    def rate_trip(self, ride_id: str, rating: int) -> Dict[str, Any]:
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
            raise LyftError("RIDE_NOT_COMPLETED", "Can only rate completed rides.")
        if rating < 1 or rating > 5:
            raise LyftError("INVALID_RATING", "Rating must be between 1 and 5.")
        ride["rating"] = rating
        return {"ride_id": ride_id, "rating": rating, "status": "rated"}

    def add_gratuity(self, ride_id: str, amount: float) -> Dict[str, Any]:
        """
        Add a tip to a completed ride.

        Args:
            ride_id (str): The ride.
            amount (float): Tip amount (must be > 0).

        Returns:
            Dict[str, Any]: ride_id, tip_amount, total_with_tip.
        """
        ride = self._require_ride(ride_id)
        if ride.get("status") != "completed":
            raise LyftError("RIDE_NOT_COMPLETED", "Can only tip on completed rides.")
        if amount <= 0:
            raise LyftError("INVALID_TIP", "Tip must be greater than zero.")
        ride["tip_amount"] = round(ride.get("tip_amount", 0) + amount, 2)
        total_with_tip = round(ride.get("fare_total", 0) + ride["tip_amount"], 2)
        return {"ride_id": ride_id, "tip_amount": ride["tip_amount"], "total_with_tip": total_with_tip}

    # ---- Round Up & Donate (Lyft-specific) ----

    def toggle_round_up(self, enabled: bool) -> Dict[str, Any]:
        """
        Enable or disable Round Up & Donate for future rides.

        Args:
            enabled (bool): True to enable, False to disable.

        Returns:
            Dict[str, Any]: round_up_enabled, status.
        """
        self.profile["round_up_enabled"] = enabled
        return {"round_up_enabled": enabled, "status": "updated"}

    def get_donation_history(self) -> Dict[str, Any]:
        """
        Get total Round Up & Donate contributions.

        Returns:
            Dict[str, Any]: total_donated, ride_count.
        """
        donations = [r.get("round_up_donation", 0)
                     for r in self.rides.values()
                     if r.get("round_up_donation", 0) > 0]
        return {
            "total_donated": round(sum(donations), 2),
            "ride_count": len(donations),
        }

    # ---- Driver ----

    def get_driver_details(self, ride_id: str) -> Dict[str, Any]:
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
            raise LyftError("NO_DRIVER", "No driver assigned to this ride yet.")
        driver = self.drivers.get(did)
        if not driver:
            raise LyftError("DRIVER_NOT_FOUND", "Driver information unavailable.")
        return deepcopy(driver)

    # ---- Offers ----

    def redeem_promo(self, offer_id: str) -> Dict[str, Any]:
        """
        Apply a promotional offer to the user's account.

        Args:
            offer_id (str): The offer to apply.

        Returns:
            Dict[str, Any]: offer_id, discount, status "applied".
        """
        offer = self.offers.get(offer_id)
        if not offer:
            raise LyftError("OFFER_NOT_FOUND", f"Offer '{offer_id}' not found.")
        if offer.get("used"):
            raise LyftError("OFFER_USED", "This offer has already been used.")
        offer["used"] = True
        promos = self.profile.get("promo", [])
        if offer_id not in promos:
            self.profile.setdefault("promo", []).append(offer_id)
        return {
            "offer_id": offer_id,
            "discount": offer.get("discount"),
            "status": "applied",
        }

    def list_promos(self) -> List[Dict[str, Any]]:
        """
        List available promotional offers.

        Returns:
            List[Dict[str, Any]]: Offer objects that have not been used.
        """
        return [deepcopy(o) for o in self.offers.values() if not o.get("used")]

    # ---- Scheduled Rides ----

    def schedule_ride(
        self, pickup: str, dropoff: str, ride_type: str,
        scheduled_time: str,
        payment_method_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Schedule a future ride.

        Args:
            pickup (str): Pickup address.
            dropoff (str): Dropoff address.
            ride_type (str): The ride type.
            scheduled_time (str): ISO-8601 scheduled pickup time.
            payment_method_id (str, optional): Payment method from profile.

        Returns:
            Dict[str, Any]: scheduled_ride_id, pickup, dropoff, ride_type,
                scheduled_time, status.
        """
        self._require_ride_type(ride_type)
        scheduled_ride_id = self._new_id("scheduled_ride")
        now = _utc_now_iso()
        self.scheduled_rides[scheduled_ride_id] = {
            "scheduled_ride_id": scheduled_ride_id,
            "pickup": pickup,
            "dropoff": dropoff,
            "ride_type": ride_type,
            "scheduled_time": scheduled_time,
            "payment_method_id": payment_method_id,
            "status": "scheduled",
            "created_at": now,
        }
        return deepcopy(self.scheduled_rides[scheduled_ride_id])

    def list_scheduled_rides(
        self, status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        List scheduled rides, optionally filtered by status.

        Args:
            status (str, optional): Filter by status
                (scheduled/cancelled/completed).

        Returns:
            List[Dict[str, Any]]: Scheduled ride objects sorted by
                scheduled_time.
        """
        results = []
        for r in self.scheduled_rides.values():
            if status and r.get("status") != status:
                continue
            results.append(deepcopy(r))
        results.sort(key=lambda x: x.get("scheduled_time", ""))
        return results

    def cancel_scheduled_ride(self, scheduled_ride_id: str) -> Dict[str, Any]:
        """
        Cancel a scheduled ride.

        Args:
            scheduled_ride_id (str): The scheduled ride to cancel.

        Returns:
            Dict[str, Any]: scheduled_ride_id, status "cancelled".
        """
        r = self.scheduled_rides.get(scheduled_ride_id)
        if not r:
            raise LyftError("SCHEDULED_RIDE_NOT_FOUND",
                            f"Scheduled ride '{scheduled_ride_id}' not found.")
        if r.get("status") == "cancelled":
            raise LyftError("ALREADY_CANCELLED",
                            "This scheduled ride is already cancelled.")
        r["status"] = "cancelled"
        return {"scheduled_ride_id": scheduled_ride_id, "status": "cancelled"}

    # ---- Wait & Save ----

    def get_wait_and_save_estimate(
        self, pickup: str, dropoff: str,
    ) -> Dict[str, Any]:
        """
        Get a Wait & Save fare estimate.

        Args:
            pickup (str): Pickup address.
            dropoff (str): Dropoff address.

        Returns:
            Dict[str, Any]: pickup, dropoff, standard_fare,
                discounted_fare, savings_amount, wait_time_minutes.
        """
        standard_fare = round(15.0 + self._rng.uniform(5, 25), 2)
        savings_pct = 0.20
        savings = round(standard_fare * savings_pct, 2)
        discounted = round(standard_fare - savings, 2)
        wait_time = self._rng.randint(5, 15)
        offer_id = self._new_id("ws_offer")
        self.wait_and_save[offer_id] = {
            "offer_id": offer_id,
            "pickup": pickup,
            "dropoff": dropoff,
            "standard_fare": standard_fare,
            "discounted_fare": discounted,
            "savings_amount": savings,
            "wait_time_minutes": wait_time,
        }
        return deepcopy(self.wait_and_save[offer_id])

    def request_wait_and_save_ride(
        self, pickup: str, dropoff: str,
        payment_method_id: Optional[str] = None,
        offer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Request a Wait & Save discounted ride.

        Args:
            pickup (str): Pickup address.
            dropoff (str): Dropoff address.
            payment_method_id (str, optional): Payment method from profile.
            offer_id (str, optional): Offer ID from a previous estimate.

        Returns:
            Dict[str, Any]: ride_id, pickup, dropoff, fare,
                wait_time_minutes, status.
        """
        if offer_id and offer_id in self.wait_and_save:
            offer = self.wait_and_save[offer_id]
            fare = offer.get("discounted_fare", 12.0)
            wait_time = offer.get("wait_time_minutes", 10)
        else:
            fare = round(12.0 + self._rng.uniform(3, 18), 2)
            wait_time = self._rng.randint(5, 15)

        ride_id = self._new_id("ride")
        now = _utc_now_iso()
        self.rides[ride_id] = {
            "ride_id": ride_id,
            "pickup": {"address": pickup},
            "dropoff": {"address": dropoff},
            "ride_type": "Standard",
            "status": "requesting",
            "fare_total": fare,
            "prime_time_pct": 0,
            "wait_and_save": True,
            "priority_pickup": False,
            "driver_id": None,
            "eta_pickup_min": wait_time,
            "eta_dropoff_min": None,
            "tip_amount": 0,
            "rating": None,
            "round_up_donation": 0,
            "created_at": now,
        }
        return {
            "ride_id": ride_id,
            "pickup": pickup,
            "dropoff": dropoff,
            "fare": fare,
            "wait_time_minutes": wait_time,
            "status": "requesting",
        }

    # ---- Ride Challenges ----

    def get_ride_challenges(self) -> List[Dict[str, Any]]:
        """
        Get active ride challenges with progress and rewards.

        Returns:
            List[Dict[str, Any]]: Challenge objects with challenge_id,
                description, progress, target, reward.
        """
        return deepcopy(self.ride_challenges)

    def get_ride_streak(self) -> Dict[str, Any]:
        """
        Get current and longest ride streak info.

        Returns:
            Dict[str, Any]: current_streak, longest_streak,
                per_streak_reward, streak_status.
        """
        return deepcopy(self.ride_streak)
