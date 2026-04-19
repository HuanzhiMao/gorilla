"""
Booking.com Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Accommodation-only platform: hotels, apartments, hostels, villas.
- User-perspective API with profile, properties, room_types, and bookings.
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .server_patch_mixin import PatchableMixin


class BookingError(Exception):
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
    "random_seed": 8001,
    "profile": {},
    "properties": {},
    "room_types": {},
    "bookings": {},
    "genius_status": {},
    "price_alerts": {},
}


class BookingAPI(PatchableMixin):
    """
    In-memory dummy Booking.com — accommodation-focused travel platform.

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

    Booking.com model: accommodation-only (hotels, apartments, hostels,
    villas), free cancellation options, property search by location,
    amenities, and rating.
    """


    def __init__(self):
        self._id_counters = {"booking": 0, "alert": 0}
        self.profile: Dict[str, Any]
        self.properties: Dict[str, Dict[str, Any]]
        self.room_types: Dict[str, Dict[str, Any]]
        self.bookings: Dict[str, Dict[str, Any]]
        self.genius_status: Dict[str, Any]
        self.price_alerts: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Booking.com API, which provides "
            "accommodation search and booking, property details, room "
            "availability, and booking management."
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
        self.genius_status = scenario.get("genius_status", DEFAULT_STATE_COPY["genius_status"])
        self.price_alerts = scenario.get("price_alerts", DEFAULT_STATE_COPY["price_alerts"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, BookingAPI):
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
        if not p: raise BookingError("PROPERTY_NOT_FOUND", f"Property '{pid}' not found.")
        return p

    def _require_room_type(self, rtid: str):
        r = self.room_types.get(rtid)
        if not r: raise BookingError("ROOM_TYPE_NOT_FOUND", f"Room type '{rtid}' not found.")
        return r

    def _require_booking(self, bid: str):
        b = self.bookings.get(bid)
        if not b: raise BookingError("BOOKING_NOT_FOUND", f"Booking '{bid}' not found.")
        return b

    # ---- User ----

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get user profile.

        Returns:
            Dict[str, Any]: name, email, phone, saved_travelers,
                payment_method.
        """
        return deepcopy(self.profile)

    # ---- Search ----

    def search_properties(
        self, city: str, check_in_date: str, check_out_date: str,
        num_guests: int = 2, min_rating: Optional[float] = None,
        max_price: Optional[float] = None, amenities: Optional[List[str]] = None,
        refundable_only: bool = False, limit: int = 20,
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
            refundable_only (bool): Only show properties with refundable rooms.
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
            if amenities:
                prop_amenities = set(a.lower() for a in prop.get("amenities", []))
                if not all(a.lower() in prop_amenities for a in amenities):
                    continue
            # Find cheapest matching room type
            cheapest = None
            has_refundable = False
            for rt in self.room_types.values():
                if rt.get("property_id") != prop["property_id"]:
                    continue
                if rt.get("max_guests", 0) < num_guests:
                    continue
                price = rt.get("base_price_per_night", 0)
                if max_price and price > max_price:
                    continue
                if rt.get("refundable"):
                    has_refundable = True
                if cheapest is None or price < cheapest:
                    cheapest = price
            if cheapest is None:
                continue
            if refundable_only and not has_refundable:
                continue
            r = deepcopy(prop)
            r["cheapest_price_per_night"] = cheapest
            results.append(r)
        results.sort(key=lambda x: x.get("review_score", 0), reverse=True)
        return results[:limit]

    def get_property(self, property_id: str) -> Dict[str, Any]:
        """
        Get full property details.

        Args:
            property_id (str): The property.

        Returns:
            Dict[str, Any]: Full property object with location, amenities,
                room_types, and policies.
        """
        return deepcopy(self._require_property(property_id))

    def get_room_types(
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

    def create_booking(
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
            raise BookingError("TOO_MANY_GUESTS", f"Room max is {rt.get('max_guests')} guests.")

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

    def cancel_booking(self, booking_id: str) -> Dict[str, Any]:
        """
        Cancel a booking.

        Args:
            booking_id (str): The booking to cancel.

        Returns:
            Dict[str, Any]: booking_id, booking_status, refund info.
        """
        b = self._require_booking(booking_id)
        if b.get("booking_status") == "cancelled":
            raise BookingError("ALREADY_CANCELLED", "This booking is already cancelled.")
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

    def get_booking(self, booking_id: str) -> Dict[str, Any]:
        """
        Get booking details.

        Args:
            booking_id (str): The booking.

        Returns:
            Dict[str, Any]: Full booking object.
        """
        return deepcopy(self._require_booking(booking_id))

    def list_bookings(self, booking_status: Optional[str] = None) -> List[Dict[str, Any]]:
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

    def modify_booking(
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
            raise BookingError("CANNOT_MODIFY", "Only confirmed bookings can be modified.")
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

    # ---- Genius Loyalty ----

    def get_genius_status(self) -> Dict[str, Any]:
        """
        Get the user's Genius loyalty status.

        Returns:
            Dict[str, Any]: level, lifetime_bookings, perks,
                bookings_to_next_level.
        """
        status = deepcopy(self.genius_status)
        level = status.get("level", 1)
        lifetime = status.get("lifetime_bookings", 0)
        perks = status.get("perks", [])
        if level < 3:
            thresholds = {1: 5, 2: 15}
            needed = thresholds.get(level, 0) - lifetime
            needed = max(0, needed)
        else:
            needed = 0
        status["bookings_to_next_level"] = needed
        return status

    def get_genius_deals(
        self, city: Optional[str] = None,
        check_in: Optional[str] = None,
        check_out: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get Genius-exclusive discounted properties.

        Args:
            city (str, optional): Filter by city.
            check_in (str, optional): Check-in date (ISO date).
            check_out (str, optional): Check-out date (ISO date).

        Returns:
            List[Dict[str, Any]]: Properties with genius_discount_percent
                and discounted prices.
        """
        level = self.genius_status.get("level", 1)
        results = []
        for prop in self.properties.values():
            discount = prop.get("genius_discount_percent", 0)
            if discount <= 0:
                continue
            if city:
                loc = prop.get("location", {})
                if not _matches_query(loc.get("city", ""), city):
                    continue
            r = deepcopy(prop)
            r["genius_discount_percent"] = discount
            r["genius_level_required"] = 1 if discount <= 10 else (2 if discount <= 15 else 3)
            if level >= r["genius_level_required"]:
                r["eligible"] = True
            else:
                r["eligible"] = False
            results.append(r)
        return results

    def apply_genius_discount(self, booking_id: str) -> Dict[str, Any]:
        """
        Apply Genius discount to an eligible booking.

        Args:
            booking_id (str): The booking to apply the discount to.

        Returns:
            Dict[str, Any]: booking_id, original_price, discounted_price,
                discount_percent, status.
        """
        b = self._require_booking(booking_id)
        if b.get("booking_status") != "confirmed":
            raise BookingError("CANNOT_APPLY_DISCOUNT",
                               "Can only apply Genius discount to confirmed bookings.")
        if b.get("genius_discount_applied"):
            raise BookingError("DISCOUNT_ALREADY_APPLIED",
                               "Genius discount already applied to this booking.")
        prop = self.properties.get(b.get("property_id", ""), {})
        discount_pct = prop.get("genius_discount_percent", 0)
        if discount_pct <= 0:
            raise BookingError("NO_GENIUS_DISCOUNT",
                               "This property does not offer a Genius discount.")
        level = self.genius_status.get("level", 1)
        required_level = 1 if discount_pct <= 10 else (2 if discount_pct <= 15 else 3)
        if level < required_level:
            raise BookingError("GENIUS_LEVEL_TOO_LOW",
                               f"Genius Level {required_level} required for this discount.",
                               context={"current_level": level, "required_level": required_level})
        original = b.get("total_price", 0)
        discount_amount = round(original * discount_pct / 100, 2)
        new_price = round(original - discount_amount, 2)
        b["total_price"] = new_price
        b["genius_discount_applied"] = True
        b["updated_at"] = _utc_now_iso()
        return {
            "booking_id": booking_id,
            "original_price": original,
            "discounted_price": new_price,
            "discount_percent": discount_pct,
            "status": "discount_applied",
        }

    # ---- Price Alerts ----

    def set_price_alert(
        self, property_id: str, check_in: str, check_out: str,
        target_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Set a price alert for a property.

        Args:
            property_id (str): The property to monitor.
            check_in (str): Check-in date (ISO date).
            check_out (str): Check-out date (ISO date).
            target_price (float, optional): Target price threshold.

        Returns:
            Dict[str, Any]: alert_id, property_id, check_in, check_out,
                target_price, status.
        """
        self._require_property(property_id)
        alert_id = self._new_id("alert")
        now = _utc_now_iso()
        # Compute current cheapest price
        cheapest = None
        for rt in self.room_types.values():
            if rt.get("property_id") != property_id:
                continue
            price = rt.get("base_price_per_night", 0)
            if cheapest is None or price < cheapest:
                cheapest = price
        self.price_alerts[alert_id] = {
            "alert_id": alert_id,
            "property_id": property_id,
            "check_in": check_in,
            "check_out": check_out,
            "target_price": target_price,
            "current_price": cheapest,
            "status": "active",
            "created_at": now,
        }
        return deepcopy(self.price_alerts[alert_id])

    def list_price_alerts(self) -> List[Dict[str, Any]]:
        """
        List active price alerts with current prices.

        Returns:
            List[Dict[str, Any]]: Active alert objects with current_price.
        """
        results = []
        for alert in self.price_alerts.values():
            if alert.get("status") != "active":
                continue
            a = deepcopy(alert)
            # Update current price
            cheapest = None
            for rt in self.room_types.values():
                if rt.get("property_id") != alert.get("property_id"):
                    continue
                price = rt.get("base_price_per_night", 0)
                if cheapest is None or price < cheapest:
                    cheapest = price
            a["current_price"] = cheapest
            results.append(a)
        return results

    def remove_price_alert(self, alert_id: str) -> Dict[str, Any]:
        """
        Remove a price alert.

        Args:
            alert_id (str): The alert to remove.

        Returns:
            Dict[str, Any]: alert_id, status "removed".
        """
        alert = self.price_alerts.get(alert_id)
        if not alert:
            raise BookingError("ALERT_NOT_FOUND", f"Price alert '{alert_id}' not found.")
        alert["status"] = "removed"
        return {"alert_id": alert_id, "status": "removed"}
