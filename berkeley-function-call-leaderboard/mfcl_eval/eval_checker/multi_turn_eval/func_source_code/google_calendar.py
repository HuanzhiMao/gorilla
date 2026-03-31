"""
Google Calendar Dummy API (in-memory, deterministic, benchmark-friendly)

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

from .server_patch_mixin import PatchableMixin


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class GoogleCalendarError(Exception):
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


DEFAULT_STATE = {
    "random_seed": 7001,
    "profile": {},
    "calendars": {},
    "events": {},
    "calendar_acls": {},
}


class GoogleCalendarAPI(PatchableMixin):
    """
    In-memory dummy implementation of Google Calendar.

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
    - calendar_acls: Dict of {calendar_id -> [{email, role, granted_at}]}

    Google Calendar model: multiple calendars, recurring events, attendee
    RSVP, Google Meet link generation, quick-add with natural language,
    reminders, free/busy queries, and calendar sharing with ACL management.
    """


    def __init__(self):
        self._id_counters = {"calendar": 0, "event": 0}
        self.profile: Dict[str, Any]
        self.calendars: Dict[str, Dict[str, Any]]
        self.events: Dict[str, Dict[str, Any]]
        self.calendar_acls: Dict[str, List[Dict[str, Any]]]
        self._api_description = (
            "This tool belongs to the Google Calendar API, which provides "
            "event scheduling, calendar management, attendee coordination, "
            "Google Meet integration, availability queries, and "
            "calendar sharing with ACL management."
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
        self.calendars = scenario.get("calendars", DEFAULT_STATE_COPY["calendars"])
        self.events = scenario.get("events", DEFAULT_STATE_COPY["events"])
        self.calendar_acls = scenario.get("calendar_acls", DEFAULT_STATE_COPY["calendar_acls"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, GoogleCalendarAPI):
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
            raise GoogleCalendarError("CALENDAR_NOT_FOUND", f"Calendar '{calendar_id}' not found.",
                                       suggested_action="Use list_calendars().")
        return cal

    def _require_event(self, event_id: str) -> Dict[str, Any]:
        ev = self.events.get(event_id)
        if not ev:
            raise GoogleCalendarError("EVENT_NOT_FOUND", f"Event '{event_id}' not found.",
                                       suggested_action="Use list_events() or search_events().")
        return ev

    def _generate_meet_link(self) -> str:
        chars = "abcdefghijklmnopqrstuvwxyz"
        code = "".join(self._rng.choices(chars, k=3)) + "-" + \
               "".join(self._rng.choices(chars, k=4)) + "-" + \
               "".join(self._rng.choices(chars, k=3))
        return f"https://meet.google.com/{code}"

    # -----------------------------------------------------------------------
    # User
    # -----------------------------------------------------------------------

    def get_calendar_settings(self) -> Dict[str, Any]:
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
        return [deepcopy(cal) for cal in self.calendars.values()]

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
            raise GoogleCalendarError("CANNOT_DELETE_PRIMARY", "Cannot delete the primary calendar.")
        # Remove events belonging to this calendar
        to_del = [eid for eid, e in self.events.items() if e.get("calendar_id") == calendar_id]
        for eid in to_del:
            del self.events[eid]
        del self.calendars[calendar_id]
        return {"calendar_id": calendar_id, "status": "deleted"}

    # -----------------------------------------------------------------------
    # Calendar Sharing (Google-exclusive)
    # -----------------------------------------------------------------------

    def share_calendar(self, calendar_id: str, email: str, role: str = "reader") -> Dict[str, Any]:
        """
        Share a calendar with another user.

        Args:
            calendar_id (str): The calendar to share.
            email (str): Email of the person to share with.
            role (str): Permission role — "reader", "writer", or "owner".
                Defaults to "reader".

        Returns:
            Dict[str, Any]: calendar_id, email, role, status "shared".
        """
        self._require_calendar(calendar_id)
        if role not in ("reader", "writer", "owner"):
            raise GoogleCalendarError("INVALID_ROLE", "Role must be 'reader', 'writer', or 'owner'.")
        acl_list = self.calendar_acls.setdefault(calendar_id, [])
        for acl in acl_list:
            if acl.get("email") == email:
                raise GoogleCalendarError("ALREADY_SHARED",
                                          f"Calendar already shared with '{email}'.")
        acl_list.append({"email": email, "role": role, "granted_at": _utc_now_iso()})
        return {"calendar_id": calendar_id, "email": email, "role": role, "status": "shared"}

    def get_calendar_acl(self, calendar_id: str) -> List[Dict[str, Any]]:
        """
        Get the access control list for a calendar.

        Args:
            calendar_id (str): The calendar.

        Returns:
            List[Dict[str, Any]]: ACL entries with email, role, granted_at.
        """
        self._require_calendar(calendar_id)
        return deepcopy(self.calendar_acls.get(calendar_id, []))

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
        generate_meet_link: bool = False,
    ) -> Dict[str, Any]:
        """
        Create a new calendar event.

        Args:
            calendar_id (str): The calendar to add the event to.
            title (str): Event title.
            start_time (str): Start time (ISO-8601).
            end_time (str): End time (ISO-8601).
            description (str, optional): Event description.
            location (str, optional): Event location.
            attendees (List[Dict], optional): List of attendees, each with
                email (str), name (str, optional).
            reminders (List[Dict], optional): Reminders, each with
                method ("popup"/"email") and minutes_before (int).
            recurrence (Dict, optional): Recurrence rule with freq
                ("daily"/"weekly"/"monthly"/"yearly"), interval (int, optional),
                by_day (List[str], optional), count (int, optional),
                until (str, optional).
            all_day (bool): Whether this is an all-day event.
            generate_meet_link (bool): Auto-create a Google Meet link.

        Returns:
            Dict[str, Any]: Created event object.
        """
        self._require_calendar(calendar_id)

        if not title:
            raise GoogleCalendarError("EMPTY_TITLE", "Event title cannot be empty.")

        meet_link = self._generate_meet_link() if generate_meet_link else None

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
            "meeting_link": meet_link,
            "created_at": now,
            "updated_at": now,
        }

        return deepcopy(self.events[event_id])

    def quick_add_event(self, calendar_id: str, text: str) -> Dict[str, Any]:
        """
        Create an event from natural language text.  Parses simple patterns
        like "Meeting with Bob tomorrow at 3pm".

        Args:
            calendar_id (str): The calendar.
            text (str): Natural language event description.

        Returns:
            Dict[str, Any]: Created event object.
        """
        self._require_calendar(calendar_id)

        now = datetime.now(timezone.utc)
        start = now + timedelta(hours=1)
        end = start + timedelta(hours=1)

        if "tomorrow" in text.lower():
            start = now + timedelta(days=1)
            start = start.replace(hour=9, minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=1)

        title = text.strip()

        return self.create_event(
            calendar_id=calendar_id,
            title=title, start_time=start.isoformat(), end_time=end.isoformat(),
        )

    def update_event(
        self, event_id: str,
        title: Optional[str] = None, start_time: Optional[str] = None,
        end_time: Optional[str] = None, description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[Dict[str, Any]]] = None,
        reminders: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing event.

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

    def delete_event(self, event_id: str) -> Dict[str, Any]:
        """
        Delete (cancel) an event.

        Args:
            event_id (str): The event to delete.

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
        time_min: Optional[str] = None, time_max: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        List events, optionally filtered by calendar and time range.

        Args:
            calendar_id (str, optional): Filter by specific calendar.
            time_min (str, optional): Only events starting after this time.
            time_max (str, optional): Only events starting before this time.
            max_results (int): Maximum events to return. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Events sorted by start time.
        """
        results = []
        for ev in self.events.values():
            if ev.get("status") == "cancelled":
                continue
            if calendar_id and ev.get("calendar_id") != calendar_id:
                continue
            if time_min and ev.get("start_time", "") < time_min:
                continue
            if time_max and ev.get("start_time", "") > time_max:
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
            raise GoogleCalendarError("INVALID_RESPONSE", "Must be 'accepted', 'declined', or 'tentative'.")

        email = self.profile.get("email", "")
        found = False
        for att in ev.get("attendees", []):
            if att.get("email") == email:
                att["response_status"] = response
                found = True
                break
        if not found:
            raise GoogleCalendarError("NOT_INVITED", "You are not an attendee of this event.")

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
                raise GoogleCalendarError("ALREADY_ATTENDEE", f"'{email}' is already an attendee.")
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
        attendees = ev.get("attendees", [])
        new_list = [a for a in attendees if a.get("email") != email]
        if len(new_list) == len(attendees):
            raise GoogleCalendarError("ATTENDEE_NOT_FOUND", f"'{email}' is not an attendee.")
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
    # Availability
    # -----------------------------------------------------------------------

    def get_free_busy(self, time_min: str, time_max: str) -> Dict[str, Any]:
        """
        Check the current user's availability in a time range.

        Args:
            time_min (str): Start of range (ISO-8601).
            time_max (str): End of range (ISO-8601).

        Returns:
            Dict[str, Any]: time_min, time_max,
                busy (List[Dict] with start and end of busy periods).
        """
        busy = []
        for ev in self.events.values():
            if ev.get("status") == "cancelled":
                continue
            if ev.get("end_time", "") <= time_min:
                continue
            if ev.get("start_time", "") >= time_max:
                continue
            busy.append({"start": ev.get("start_time"), "end": ev.get("end_time")})

        busy.sort(key=lambda x: x["start"])
        return {"time_min": time_min, "time_max": time_max, "busy": busy}

    def move_event(self, event_id: str, new_calendar_id: str) -> Dict[str, Any]:
        """
        Move an event to a different calendar.

        Args:
            event_id (str): The event to move.
            new_calendar_id (str): The destination calendar.

        Returns:
            Dict[str, Any]: event_id, calendar_id, status "moved".
        """
        ev = self._require_event(event_id)
        self._require_calendar(new_calendar_id)
        ev["calendar_id"] = new_calendar_id
        ev["updated_at"] = _utc_now_iso()
        return {"event_id": event_id, "calendar_id": new_calendar_id, "status": "moved"}
