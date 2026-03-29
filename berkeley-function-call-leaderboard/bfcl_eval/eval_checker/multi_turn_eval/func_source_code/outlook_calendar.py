"""
Outlook Calendar Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- User-perspective API with profile, calendars, and events.
"""

from __future__ import annotations

import copy
import random
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .base_service import BaseServiceAPI


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class OutlookCalendarError(Exception):
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _matches_query(text: str, query: str) -> bool:
    q = (query or "").strip().lower()
    if not q:
        return True
    return q in (text or "").lower()


# ---------------------------------------------------------------------------
# Outlook Calendar API
# ---------------------------------------------------------------------------


DEFAULT_STATE = {
    "random_seed": 7002,
    "profile": {},
    "calendars": {},
    "events": {},
    "room_resources": [],
    "categories": [],
    "working_hours": {},
}


class OutlookCalendarAPI(BaseServiceAPI):
    """
    In-memory dummy implementation of Outlook Calendar.

    State variables:
    - profile: {name, email, timezone}
    - calendars: Dict of {calendar_id -> {calendar_id, name, is_primary}}
    - events: Dict of {event_id -> {event_id, calendar_id, title,
      description?, location?, start_time, end_time, all_day?,
      status{confirmed|tentative|cancelled}, organizer{email, name?},
      attendees[{email, name?, response_status}],
      reminders?[{method, minutes_before}],
      recurrence?{freq, interval?, by_day?, count?, until?},
      recurring_event_id?, meeting_link?, created_at, updated_at}}
    - room_resources: List of {room_id, name, capacity, floor, equipment[]}
    - categories: List of {name, color}
    - working_hours: Dict of {days[], start_time, end_time, timezone}

    Outlook Calendar model: multiple calendars, recurring events, attendee
    RSVP, Teams meeting link generation, scheduling assistant for finding
    meeting times, schedule queries, room booking, event categories, and
    working hours management.
    """

    _STATE_KEYS = ("profile", "calendars", "events", "room_resources", "categories", "working_hours")
    _ID_COUNTER_DEFAULTS = {"calendar": 0, "event": 0}
    _DEFAULT_SEED = 7002

    def __init__(self):
        super().__init__()
        self.profile: Dict[str, Any]
        self.calendars: Dict[str, Dict[str, Any]]
        self.events: Dict[str, Dict[str, Any]]
        self.room_resources: List[Dict[str, Any]]
        self.categories: List[Dict[str, Any]]
        self.working_hours: Dict[str, Any]
        self._api_description = (
            "This tool belongs to the Outlook Calendar API, which provides "
            "event scheduling, calendar management, attendee coordination, "
            "Teams meeting integration, scheduling assistant, "
            "availability queries, room booking, event categories, and "
            "working hours management."
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
        self.calendars = scenario.get("calendars", DEFAULT_STATE_COPY["calendars"])
        self.events = scenario.get("events", DEFAULT_STATE_COPY["events"])
        self.room_resources = scenario.get("room_resources", DEFAULT_STATE_COPY["room_resources"])
        self.categories = scenario.get("categories", DEFAULT_STATE_COPY["categories"])
        self.working_hours = scenario.get("working_hours", DEFAULT_STATE_COPY["working_hours"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, OutlookCalendarAPI):
            return False

        for attr_name in vars(self):
            if attr_name.startswith("_"):
                continue
            model_attr = getattr(self, attr_name)
            ground_truth_attr = getattr(value, attr_name)

            if model_attr != ground_truth_attr:
                return False

        return True

    # -----------------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------------

    def _require_calendar(self, calendar_id: str) -> Dict[str, Any]:
        cal = self.calendars.get(calendar_id)
        if not cal:
            raise OutlookCalendarError("CALENDAR_NOT_FOUND", f"Calendar '{calendar_id}' not found.")
        return cal

    def _require_event(self, event_id: str) -> Dict[str, Any]:
        ev = self.events.get(event_id)
        if not ev:
            raise OutlookCalendarError("EVENT_NOT_FOUND", f"Event '{event_id}' not found.")
        return ev

    def _generate_teams_link(self) -> str:
        code = "".join(self._rng.choices("0123456789abcdef", k=12))
        return f"https://teams.microsoft.com/l/meetup-join/{code}"

    # -----------------------------------------------------------------------
    # User
    # -----------------------------------------------------------------------

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get the current user's profile.

        Returns:
            Dict[str, Any]: name, email, timezone.
        """
        return deepcopy(self.profile)

    # -----------------------------------------------------------------------
    # Calendar management
    # -----------------------------------------------------------------------

    def list_calendars(self) -> List[Dict[str, Any]]:
        """
        List all calendars for the current user.

        Returns:
            List[Dict[str, Any]]: Calendar objects with calendar_id, name,
                is_primary.
        """
        return [deepcopy(c) for c in self.calendars.values()]

    def create_calendar(self, name: str) -> Dict[str, Any]:
        """
        Create a new calendar.

        Args:
            name (str): Calendar name.

        Returns:
            Dict[str, Any]: calendar_id, name, is_primary.
        """
        cal_id = self._new_id("calendar")
        self.calendars[cal_id] = {
            "calendar_id": cal_id, "name": name, "is_primary": False,
        }
        return deepcopy(self.calendars[cal_id])

    def delete_calendar(self, calendar_id: str) -> Dict[str, Any]:
        """
        Delete a non-primary calendar and all its events.

        Args:
            calendar_id (str): The calendar to delete.

        Returns:
            Dict[str, Any]: calendar_id, status "deleted".
        """
        cal = self._require_calendar(calendar_id)
        if cal.get("is_primary"):
            raise OutlookCalendarError("CANNOT_DELETE_PRIMARY", "Cannot delete the primary calendar.")
        to_del = [eid for eid, e in self.events.items() if e.get("calendar_id") == calendar_id]
        for eid in to_del:
            del self.events[eid]
        del self.calendars[calendar_id]
        return {"calendar_id": calendar_id, "status": "deleted"}

    # -----------------------------------------------------------------------
    # Events
    # -----------------------------------------------------------------------

    def create_event(
        self,
        calendar_id: str,
        title: str,
        start_time: str,
        end_time: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[Dict[str, Any]]] = None,
        reminders: Optional[List[Dict[str, Any]]] = None,
        recurrence: Optional[Dict[str, Any]] = None,
        all_day: bool = False,
        generate_teams_link: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a calendar event.

        Args:
            calendar_id (str): The calendar.
            title (str): Event title.
            start_time (str): Start time (ISO-8601).
            end_time (str): End time (ISO-8601).
            description (str, optional): Event description.
            location (str, optional): Location.
            attendees (List[Dict], optional): Each with email (str),
                name (str, optional).
            reminders (List[Dict], optional): Each with method
                ("popup"/"email") and minutes_before (int).
            recurrence (Dict, optional): Recurrence rule with freq
                ("daily"/"weekly"/"monthly"/"yearly"), interval (int, optional),
                by_day (List[str], optional), count (int, optional),
                until (str, optional).
            all_day (bool): All-day event.
            generate_teams_link (bool): Generate a Teams meeting link.

        Returns:
            Dict[str, Any]: Created event object.
        """
        self._require_calendar(calendar_id)

        if not title:
            raise OutlookCalendarError("EMPTY_TITLE", "Event title cannot be empty.")

        teams_link = self._generate_teams_link() if generate_teams_link else None

        attendee_list = []
        for att in (attendees or []):
            attendee_list.append({
                "email": att.get("email", ""),
                "name": att.get("name", ""),
                "response_status": "needs_action",
            })

        now = _utc_now_iso()
        event_id = self._new_id("event")
        self.events[event_id] = {
            "event_id": event_id,
            "calendar_id": calendar_id,
            "title": title,
            "description": description or "",
            "location": location,
            "start_time": start_time,
            "end_time": end_time,
            "all_day": all_day,
            "status": "confirmed",
            "organizer": {
                "email": self.profile.get("email", ""),
                "name": self.profile.get("name", ""),
            },
            "attendees": attendee_list,
            "reminders": reminders or [],
            "recurrence": recurrence,
            "recurring_event_id": None,
            "meeting_link": teams_link,
            "created_at": now,
            "updated_at": now,
        }

        return deepcopy(self.events[event_id])

    def update_event(
        self, event_id: str,
        title: Optional[str] = None, start_time: Optional[str] = None,
        end_time: Optional[str] = None, description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[Dict[str, Any]]] = None,
        reminders: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Update an event's properties.

        Args:
            event_id (str): The event to update.
            title (str, optional): New title.
            start_time (str, optional): New start time.
            end_time (str, optional): New end time.
            description (str, optional): New description.
            location (str, optional): New location.
            attendees (List[Dict], optional): Replace attendee list, each with
                email (str), name (str, optional).
            reminders (List[Dict], optional): Replace reminders, each with
                method and minutes_before.

        Returns:
            Dict[str, Any]: Updated event object.
        """
        ev = self._require_event(event_id)
        if title is not None:
            ev["title"] = title
        if start_time is not None:
            ev["start_time"] = start_time
        if end_time is not None:
            ev["end_time"] = end_time
        if description is not None:
            ev["description"] = description
        if location is not None:
            ev["location"] = location
        if attendees is not None:
            ev["attendees"] = [
                {"email": a.get("email", ""), "name": a.get("name", ""), "response_status": "needs_action"}
                for a in attendees
            ]
        if reminders is not None:
            ev["reminders"] = reminders
        ev["updated_at"] = _utc_now_iso()
        return deepcopy(ev)

    def cancel_event(self, event_id: str) -> Dict[str, Any]:
        """
        Cancel an event.

        Args:
            event_id (str): The event to cancel.

        Returns:
            Dict[str, Any]: event_id, status "cancelled".
        """
        ev = self._require_event(event_id)
        ev["status"] = "cancelled"
        ev["updated_at"] = _utc_now_iso()
        return {"event_id": event_id, "status": "cancelled"}

    def get_event(self, event_id: str) -> Dict[str, Any]:
        """
        Get full event details.

        Args:
            event_id (str): The event.

        Returns:
            Dict[str, Any]: Full event object.
        """
        return deepcopy(self._require_event(event_id))

    def list_events(
        self, calendar_id: Optional[str] = None,
        start_date: Optional[str] = None, end_date: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List events, optionally filtered by calendar and date range.

        Args:
            calendar_id (str, optional): Filter by calendar.
            start_date (str, optional): Only events starting after this.
            end_date (str, optional): Only events starting before this.
            max_results (int): Max results.

        Returns:
            List[Dict[str, Any]]: Events sorted by start time.
        """
        results = []
        for ev in self.events.values():
            if ev.get("status") == "cancelled":
                continue
            if calendar_id and ev.get("calendar_id") != calendar_id:
                continue
            if start_date and ev.get("start_time", "") < start_date:
                continue
            if end_date and ev.get("start_time", "") > end_date:
                continue
            results.append(deepcopy(ev))
        results.sort(key=lambda x: x.get("start_time", ""))
        return results[:max_results]

    def search_events(
        self, query: str, calendar_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search events by text query across title, description, and location.

        Args:
            query (str): Search text.
            calendar_id (str, optional): Limit to specific calendar.

        Returns:
            List[Dict[str, Any]]: Matching events.
        """
        results = []
        for ev in self.events.values():
            if ev.get("status") == "cancelled":
                continue
            if calendar_id and ev.get("calendar_id") != calendar_id:
                continue
            text = f"{ev.get('title', '')} {ev.get('description', '')} {ev.get('location', '')}"
            if _matches_query(text, query):
                results.append(deepcopy(ev))
        results.sort(key=lambda x: x.get("start_time", ""))
        return results

    # -----------------------------------------------------------------------
    # Attendees & RSVP
    # -----------------------------------------------------------------------

    def rsvp_event(self, event_id: str, response: str) -> Dict[str, Any]:
        """
        RSVP to an event invitation.

        Args:
            event_id (str): The event.
            response (str): "accepted", "declined", or "tentative".

        Returns:
            Dict[str, Any]: event_id, response, status.
        """
        ev = self._require_event(event_id)
        if response not in ("accepted", "declined", "tentative"):
            raise OutlookCalendarError("INVALID_RESPONSE", "Must be 'accepted', 'declined', or 'tentative'.")

        email = self.profile.get("email", "")
        found = False
        for att in ev.get("attendees", []):
            if att.get("email") == email:
                att["response_status"] = response
                found = True
                break
        if not found:
            raise OutlookCalendarError("NOT_ATTENDEE", "You are not an attendee.")

        ev["updated_at"] = _utc_now_iso()
        return {"event_id": event_id, "response": response, "status": "updated"}

    def add_attendee(
        self, event_id: str, email: str, name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Add an attendee to an event.

        Args:
            event_id (str): The event.
            email (str): Attendee's email.
            name (str, optional): Attendee's name.

        Returns:
            Dict[str, Any]: event_id, email, status "added".
        """
        ev = self._require_event(event_id)
        for att in ev.get("attendees", []):
            if att.get("email") == email:
                raise OutlookCalendarError("ALREADY_ATTENDEE", f"'{email}' is already an attendee.")
        ev.setdefault("attendees", []).append({
            "email": email, "name": name or "", "response_status": "needs_action",
        })
        ev["updated_at"] = _utc_now_iso()
        return {"event_id": event_id, "email": email, "status": "added"}

    def remove_attendee(self, event_id: str, email: str) -> Dict[str, Any]:
        """
        Remove an attendee from an event.

        Args:
            event_id (str): The event.
            email (str): Attendee's email to remove.

        Returns:
            Dict[str, Any]: event_id, email, status "removed".
        """
        ev = self._require_event(event_id)
        new_list = [a for a in ev.get("attendees", []) if a.get("email") != email]
        if len(new_list) == len(ev.get("attendees", [])):
            raise OutlookCalendarError("ATTENDEE_NOT_FOUND", f"'{email}' is not an attendee.")
        ev["attendees"] = new_list
        ev["updated_at"] = _utc_now_iso()
        return {"event_id": event_id, "email": email, "status": "removed"}

    def set_event_reminder(self, event_id: str, reminders: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Set reminders for an event.

        Args:
            event_id (str): The event.
            reminders (List[Dict]): Reminders with method ("popup"/"email")
                and minutes_before (int).

        Returns:
            Dict[str, Any]: event_id, reminders, status.
        """
        ev = self._require_event(event_id)
        ev["reminders"] = reminders
        ev["updated_at"] = _utc_now_iso()
        return {"event_id": event_id, "reminders": reminders, "status": "updated"}

    # -----------------------------------------------------------------------
    # Scheduling assistant
    # -----------------------------------------------------------------------

    def find_meeting_times(
        self, attendee_emails: List[str],
        duration_minutes: int, time_min: str, time_max: str,
    ) -> Dict[str, Any]:
        """
        Find available meeting times when all attendees are free.

        Args:
            attendee_emails (List[str]): Attendee emails to check.
            duration_minutes (int): Required meeting duration.
            time_min (str): Search window start (ISO-8601).
            time_max (str): Search window end (ISO-8601).

        Returns:
            Dict[str, Any]: suggestions (List[Dict]) each with start, end,
                confidence (str "good"/"fair"/"poor").
        """
        try:
            t_min = datetime.fromisoformat(time_min.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            t_min = datetime.now(timezone.utc)
        try:
            t_max = datetime.fromisoformat(time_max.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            t_max = t_min + timedelta(days=5)

        suggestions = []
        slot_start = t_min
        while slot_start + timedelta(minutes=duration_minutes) <= t_max and len(suggestions) < 3:
            slot_end = slot_start + timedelta(minutes=duration_minutes)
            if 9 <= slot_start.hour < 17:
                confidence = "good" if slot_start.hour < 12 else "fair"
                suggestions.append({
                    "start": slot_start.isoformat(),
                    "end": slot_end.isoformat(),
                    "confidence": confidence,
                })
            slot_start += timedelta(hours=1)

        return {"suggestions": suggestions}

    # -----------------------------------------------------------------------
    # Availability
    # -----------------------------------------------------------------------

    def get_schedule(
        self, start_date: str, end_date: str,
    ) -> Dict[str, Any]:
        """
        Get the current user's schedule for a date range.

        Args:
            start_date (str): Start of range (ISO-8601).
            end_date (str): End of range (ISO-8601).

        Returns:
            Dict[str, Any]: schedule (List[Dict] with start, end,
                title, status for each event).
        """
        schedule = []
        for ev in self.events.values():
            if ev.get("status") == "cancelled":
                continue
            if ev.get("end_time", "") <= start_date:
                continue
            if ev.get("start_time", "") >= end_date:
                continue
            schedule.append({
                "start": ev.get("start_time"),
                "end": ev.get("end_time"),
                "title": ev.get("title"),
                "status": ev.get("status", "confirmed"),
            })
        schedule.sort(key=lambda x: x["start"])
        return {"schedule": schedule}

    # -----------------------------------------------------------------------
    # Room Management (Outlook-exclusive)
    # -----------------------------------------------------------------------

    def list_rooms(self) -> List[Dict[str, Any]]:
        """
        List available conference rooms.

        Returns:
            List[Dict[str, Any]]: Room resources with room_id, name, capacity,
                floor, equipment.
        """
        return deepcopy(self.room_resources)

    def book_room(self, room_id: str, event_id: str) -> Dict[str, Any]:
        """
        Book a conference room for an existing event.

        Args:
            room_id (str): The room resource ID.
            event_id (str): The event to attach the room to.

        Returns:
            Dict[str, Any]: room_id, event_id, room_name, status "booked".
        """
        ev = self._require_event(event_id)
        room = None
        for r in self.room_resources:
            if r.get("room_id") == room_id:
                room = r
                break
        if not room:
            raise OutlookCalendarError("ROOM_NOT_FOUND",
                                       f"Room '{room_id}' not found.",
                                       suggested_action="Use list_rooms() to see available rooms.")
        ev["location"] = room.get("name", room_id)
        ev["room_id"] = room_id
        ev["updated_at"] = _utc_now_iso()
        return {"room_id": room_id, "event_id": event_id,
                "room_name": room.get("name"), "status": "booked"}

    # -----------------------------------------------------------------------
    # Working Hours (Outlook-exclusive)
    # -----------------------------------------------------------------------

    def set_working_hours(self, days: List[str], start_time: str,
                          end_time: str, timezone: str) -> Dict[str, Any]:
        """
        Set the user's working hours.

        Args:
            days (List[str]): Working days (e.g., ["Monday", "Tuesday"]).
            start_time (str): Start time (e.g., "09:00").
            end_time (str): End time (e.g., "17:00").
            timezone (str): Timezone identifier (e.g., "America/Chicago").

        Returns:
            Dict[str, Any]: Updated working hours with days, start_time,
                end_time, timezone.
        """
        self.working_hours = {
            "days": days, "start_time": start_time,
            "end_time": end_time, "timezone": timezone,
        }
        return deepcopy(self.working_hours)

    # -----------------------------------------------------------------------
    # Categories (Outlook-exclusive)
    # -----------------------------------------------------------------------

    def set_category(self, event_id: str, category: str) -> Dict[str, Any]:
        """
        Set a category tag on an event.

        Args:
            event_id (str): The event to tag.
            category (str): Category name (e.g., "Urgent", "Travel").

        Returns:
            Dict[str, Any]: event_id, category, status "tagged".
        """
        ev = self._require_event(event_id)
        categories = ev.setdefault("categories", [])
        if category not in categories:
            categories.append(category)
        ev["updated_at"] = _utc_now_iso()
        return {"event_id": event_id, "category": category, "status": "tagged"}

    def list_categories(self) -> List[Dict[str, Any]]:
        """
        List available event categories.

        Returns:
            List[Dict[str, Any]]: Categories with name and color.
        """
        return deepcopy(self.categories)
