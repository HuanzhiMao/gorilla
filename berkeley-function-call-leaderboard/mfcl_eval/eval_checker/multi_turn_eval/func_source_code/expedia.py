"""
Expedia Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Accommodation-focused travel platform with property search, room booking,
  saved traveler profiles, and booking management.
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .server_patch_mixin import PatchableMixin


class ExpediaError(Exception):
    def __init__(self, error_code: str, message: str,
                 suggested_action: str = "", context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.error = {"error_code": error_code, "message": message,
                      "suggested_action": suggested_action, "context": context or {}}

    def to_dict(self) -> Dict[str, Any]:
        return copy.deepcopy(self.error)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _matches_query(text: str, query: str) -> bool:
    q = (query or "").strip().lower()
    return not q or q in (text or "").lower()


DEFAULT_STATE = {
    "random_seed": 8002,
    "profile": {},
    "properties": {},
    "room_types": {},
    "bookings": {},
}


class ExpediaAPI(PatchableMixin):
    """
    In-memory dummy Expedia — accommodation-focused travel platform.

    State variables:
    - profile: {name, email, phone?, saved_travelers?, payment_method[]}
    - properties: Dict of {property_id -> {property_id, name,
      location{city, region?, country, address?}, star_rating?,
      review_score?, amenities[], room_types[],
      policies{check_in_time?, check_out_time?,
      cancellation_policy_summary?}}}
    - room_types: Dict of {room_type_id -> {room_type_id, property_id,
      name, max_guests, bed_type?, amenities[], base_price_per_night,
      taxes_and_fees?, inventory_by_date?, refundable?,
      breakfast_included?}}
    - bookings: Dict of {booking_id -> {booking_id, property_id,
      room_type_id, guest_info{name, email, phone?}, check_in_date,
      check_out_date, num_guests, rooms_booked, total_price,
      payment_status, booking_status, cancellation_policy_snapshot?,
      special_requests?, created_at, updated_at}}

    Expedia model: accommodation-focused with saved traveler profiles,
    property search by location, amenities, star rating, and review score.
    """


    def __init__(self):
        self._id_counters = {"booking": 0}
        self.profile: Dict[str, Any]
        self.properties: Dict[str, Dict[str, Any]]
        self.room_types: Dict[str, Dict[str, Any]]
        self.bookings: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Expedia API, which provides "
            "accommodation search and booking, property details, room "
            "availability, traveler management, and booking management."
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
        self._random = random.Random(
            scenario.get("random_seed", DEFAULT_STATE_COPY["random_seed"])
        )
        self.profile = scenario.get("profile", DEFAULT_STATE_COPY["profile"])
        self.properties = scenario.get("properties", DEFAULT_STATE_COPY["properties"])
        self.room_types = scenario.get("room_types", DEFAULT_STATE_COPY["room_types"])
        self.bookings = scenario.get("bookings", DEFAULT_STATE_COPY["bookings"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, ExpediaAPI):
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

    def _require_property(self, pid: str):
        p = self.properties.get(pid)
        if not p: raise ExpediaError("PROPERTY_NOT_FOUND", f"Property '{pid}' not found.")
        return p

    def _require_room_type(self, rtid: str):
        r = self.room_types.get(rtid)
        if not r: raise ExpediaError("ROOM_TYPE_NOT_FOUND", f"Room type '{rtid}' not found.")
        return r

    def _require_booking(self, bid: str):
        b = self.bookings.get(bid)
        if not b: raise ExpediaError("BOOKING_NOT_FOUND", f"Booking '{bid}' not found.")
        return b

    # ---- User ----

    def get_traveler_profile(self) -> Dict[str, Any]:
        """
        Get user profile.

        Returns:
            Dict[str, Any]: name, email, phone, saved_travelers,
                payment_method.
        """
        return deepcopy(self.profile)

    def add_saved_traveler(
        self, name: str, email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add a saved traveler to the profile for quick booking.

        Args:
            name (str): Traveler's name.
            email (str, optional): Traveler's email.
            phone (str, optional): Traveler's phone.

        Returns:
            Dict[str, Any]: name, status "added".
        """
        traveler = {"name": name}
        if email:
            traveler["email"] = email
        if phone:
            traveler["phone"] = phone
        self.profile.setdefault("saved_travelers", []).append(traveler)
        return {"name": name, "status": "added"}

    def remove_saved_traveler(self, name: str) -> Dict[str, Any]:
        """
        Remove a saved traveler from the profile.

        Args:
            name (str): Traveler's name to remove.

        Returns:
            Dict[str, Any]: name, status "removed".
        """
        travelers = self.profile.get("saved_travelers", [])
        new_list = [t for t in travelers if t.get("name") != name]
        if len(new_list) == len(travelers):
            raise ExpediaError("TRAVELER_NOT_FOUND", f"Saved traveler '{name}' not found.")
        self.profile["saved_travelers"] = new_list
        return {"name": name, "status": "removed"}

    # ---- Search ----

    def search_hotels(
        self, city: str, check_in_date: str, check_out_date: str,
        num_guests: int = 2, min_rating: Optional[float] = None,
        max_price: Optional[float] = None, amenities: Optional[List[str]] = None,
        star_rating: Optional[int] = None, limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search for accommodation properties.

        Args:
            city (str): City name to search in.
            check_in_date (str): Check-in date (ISO date).
            check_out_date (str): Check-out date (ISO date).
            num_guests (int): Number of guests. Defaults to 2.
            min_rating (float, optional): Minimum review score.
            max_price (float, optional): Maximum base price per night.
            amenities (List[str], optional): Required amenities.
            star_rating (int, optional): Minimum star rating.
            limit (int): Maximum results. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Matching properties with cheapest room price.
        """
        results = []
        for prop in self.properties.values():
            loc = prop.get("location", {})
            if not _matches_query(loc.get("city", ""), city):
                continue
            if min_rating and prop.get("review_score", 0) < min_rating:
                continue
            if star_rating and prop.get("star_rating", 0) < star_rating:
                continue
            if amenities:
                prop_amenities = set(a.lower() for a in prop.get("amenities", []))
                if not all(a.lower() in prop_amenities for a in amenities):
                    continue
            # Find cheapest matching room type
            cheapest = None
            for rt in self.room_types.values():
                if rt.get("property_id") != prop["property_id"]:
                    continue
                if rt.get("max_guests", 0) < num_guests:
                    continue
                price = rt.get("base_price_per_night", 0)
                if max_price and price > max_price:
                    continue
                if cheapest is None or price < cheapest:
                    cheapest = price
            if cheapest is None:
                continue
            r = deepcopy(prop)
            r["cheapest_price_per_night"] = cheapest
            results.append(r)
        results.sort(key=lambda x: x.get("review_score", 0), reverse=True)
        return results[:limit]

    def get_hotel_details(self, property_id: str) -> Dict[str, Any]:
        """
        Get full property details.

        Args:
            property_id (str): The property.

        Returns:
            Dict[str, Any]: Full property object with location, amenities,
                room_types, and policies.
        """
        return deepcopy(self._require_property(property_id))

    def get_room_availability(
        self, property_id: str, check_in_date: str, check_out_date: str,
        num_guests: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        List available room types for a property.

        Args:
            property_id (str): The property.
            check_in_date (str): Check-in date.
            check_out_date (str): Check-out date.
            num_guests (int): Number of guests.

        Returns:
            List[Dict[str, Any]]: Available room type objects.
        """
        self._require_property(property_id)
        results = []
        for rt in self.room_types.values():
            if rt.get("property_id") != property_id:
                continue
            if rt.get("max_guests", 0) < num_guests:
                continue
            results.append(deepcopy(rt))
        return results

    # ---- Bookings ----

    def create_itinerary(
        self, room_type_id: str, check_in_date: str, check_out_date: str,
        num_guests: int, rooms_booked: int = 1,
        guest_name: Optional[str] = None, guest_email: Optional[str] = None,
        guest_phone: Optional[str] = None,
        special_requests: Optional[str] = None,
        payment_method_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Book a room.

        Args:
            room_type_id (str): The room type to book.
            check_in_date (str): Check-in date (ISO date).
            check_out_date (str): Check-out date (ISO date).
            num_guests (int): Number of guests.
            rooms_booked (int): Number of rooms. Defaults to 1.
            guest_name (str, optional): Guest name. Defaults to profile name.
            guest_email (str, optional): Guest email. Defaults to profile email.
            guest_phone (str, optional): Guest phone.
            special_requests (str, optional): Special requests.
            payment_method_id (str, optional): Payment method from profile.

        Returns:
            Dict[str, Any]: Created booking object.
        """
        rt = self._require_room_type(room_type_id)
        prop = self._require_property(rt.get("property_id", ""))

        if rt.get("max_guests", 0) < num_guests:
            raise ExpediaError("TOO_MANY_GUESTS", f"Room max is {rt.get('max_guests')} guests.")

        try:
            ci = datetime.fromisoformat(check_in_date)
            co = datetime.fromisoformat(check_out_date)
            nights = max(1, (co - ci).days)
        except (ValueError, TypeError):
            nights = 1

        base_price = rt.get("base_price_per_night", 0) * nights * rooms_booked
        taxes = rt.get("taxes_and_fees", 0) * nights * rooms_booked
        total = round(base_price + taxes, 2)

        cancellation_snapshot = None
        if rt.get("refundable"):
            policies = prop.get("policies", {})
            cancellation_snapshot = policies.get(
                "cancellation_policy_summary", "Free cancellation until 1 day before check-in"
            )

        now = _utc_now_iso()
        booking_id = self._new_id("booking")
        self.bookings[booking_id] = {
            "booking_id": booking_id,
            "property_id": prop["property_id"],
            "room_type_id": room_type_id,
            "guest_info": {
                "name": guest_name or self.profile.get("name", ""),
                "email": guest_email or self.profile.get("email", ""),
                "phone": guest_phone or self.profile.get("phone"),
            },
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "num_guests": num_guests,
            "rooms_booked": rooms_booked,
            "total_price": total,
            "payment_status": "paid" if payment_method_id else "pending",
            "booking_status": "confirmed",
            "cancellation_policy_snapshot": cancellation_snapshot,
            "special_requests": special_requests,
            "created_at": now,
            "updated_at": now,
        }
        return deepcopy(self.bookings[booking_id])

    def cancel_itinerary(self, booking_id: str) -> Dict[str, Any]:
        """
        Cancel a booking.

        Args:
            booking_id (str): The booking to cancel.

        Returns:
            Dict[str, Any]: booking_id, booking_status, refund info.
        """
        b = self._require_booking(booking_id)
        if b.get("booking_status") == "cancelled":
            raise ExpediaError("ALREADY_CANCELLED", "This booking is already cancelled.")
        b["booking_status"] = "cancelled"
        b["updated_at"] = _utc_now_iso()
        refundable = b.get("cancellation_policy_snapshot") is not None
        refund = b.get("total_price", 0) if refundable else 0
        if refundable:
            b["payment_status"] = "refunded"
        else:
            b["payment_status"] = "no_refund"
        return {
            "booking_id": booking_id,
            "booking_status": "cancelled",
            "refund_amount": refund,
            "refundable": refundable,
        }

    def get_itinerary(self, booking_id: str) -> Dict[str, Any]:
        """
        Get booking details.

        Args:
            booking_id (str): The booking.

        Returns:
            Dict[str, Any]: Full booking object.
        """
        return deepcopy(self._require_booking(booking_id))

    def list_trips(self, booking_status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List bookings, optionally filtered by status.

        Args:
            booking_status (str, optional): Filter by status
                (confirmed/cancelled).

        Returns:
            List[Dict[str, Any]]: Bookings sorted by check-in date.
        """
        results = []
        for b in self.bookings.values():
            if booking_status and b.get("booking_status") != booking_status:
                continue
            results.append(deepcopy(b))
        results.sort(key=lambda x: x.get("check_in_date", ""))
        return results

    def update_itinerary(
        self, booking_id: str,
        check_in_date: Optional[str] = None,
        check_out_date: Optional[str] = None,
        num_guests: Optional[int] = None,
        rooms_booked: Optional[int] = None,
        special_requests: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Modify a confirmed booking.

        Args:
            booking_id (str): The booking to modify.
            check_in_date (str, optional): New check-in date.
            check_out_date (str, optional): New check-out date.
            num_guests (int, optional): New guest count.
            rooms_booked (int, optional): New room count.
            special_requests (str, optional): New special requests.

        Returns:
            Dict[str, Any]: Updated booking object.
        """
        b = self._require_booking(booking_id)
        if b.get("booking_status") != "confirmed":
            raise ExpediaError("CANNOT_MODIFY", "Only confirmed bookings can be modified.")
        if check_in_date:
            b["check_in_date"] = check_in_date
        if check_out_date:
            b["check_out_date"] = check_out_date
        if num_guests is not None:
            b["num_guests"] = num_guests
        if rooms_booked is not None:
            b["rooms_booked"] = rooms_booked
        if special_requests is not None:
            b["special_requests"] = special_requests
        b["updated_at"] = _utc_now_iso()
        return deepcopy(b)
