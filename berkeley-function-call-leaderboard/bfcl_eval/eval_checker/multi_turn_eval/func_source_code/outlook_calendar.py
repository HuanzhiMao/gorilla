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

from .server_patch_mixin import PatchableMixin


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
    "categories": [],
    "working_hours": {},
    "scheduling_polls": {},
    "rooms": {},
}


class OutlookCalendarAPI(PatchableMixin):
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
    - rooms: Dict of {room_id -> {room_id, name, capacity, building?,
      floor, equipment[]}}
    - categories: List of {name, color}
    - working_hours: Dict of {days[], start_time, end_time, timezone}

    Outlook Calendar model: multiple calendars, recurring events, attendee
    RSVP, Teams meeting link generation, scheduling assistant for finding
    meeting times, schedule queries, room booking, event categories, and
    working hours management.
    """


    def __init__(self):
        self._id_counters = {"calendar": 0, "event": 0, "poll": 0}
        self.profile: Dict[str, Any]
        self.calendars: Dict[str, Dict[str, Any]]
        self.events: Dict[str, Dict[str, Any]]
        self.categories: List[Dict[str, Any]]
        self.working_hours: Dict[str, Any]
        self.scheduling_polls: Dict[str, Dict[str, Any]]
        self.rooms: Dict[str, Dict[str, Any]]
        self._api_description = (
            "This tool belongs to the Outlook Calendar API, which provides "
            "event scheduling, calendar management, attendee coordination, "
            "Teams meeting integration, scheduling assistant, "
            "availability queries, room booking, event categories, and "
            "working hours management."
        )


    def _new_id(self, prefix: str) -> str:
        """Generate the next sequential ID for *prefix* (e.g. ``order_1``)."""
        self._id_counters[prefix] = self._id_counters.get(prefix, 0) + 1
        return f"{prefix}_{self._id_counters[prefix]}"

    def _load_scenario(
        self,
        scenario: Dict[str, Any],
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
        self.categories = scenario.get("categories", DEFAULT_STATE_COPY["categories"])
        self.working_hours = scenario.get("working_hours", DEFAULT_STATE_COPY["working_hours"])
        self.scheduling_polls = scenario.get("scheduling_polls", DEFAULT_STATE_COPY["scheduling_polls"])
        self.rooms = scenario.get("rooms", DEFAULT_STATE_COPY["rooms"])

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

    def get_calendar_profile(self) -> Dict[str, Any]:
        """
        Get the current user's Outlook Calendar profile.

        Returns:
            Dict[str, Any]: name, email, timezone.
        """
        return deepcopy(self.profile)

    # -----------------------------------------------------------------------
    # Calendar management
    # -----------------------------------------------------------------------

    def get_calendars(self) -> List[Dict[str, Any]]:
        """
        Get all calendars for the current user.

        Returns:
            List[Dict[str, Any]]: Calendar objects with calendar_id, name,
                is_primary.
        """
        return [deepcopy(c) for c in self.calendars.values()]

    def new_calendar(self, name: str) -> Dict[str, Any]:
        """
        Create a new Outlook calendar.

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

    def remove_calendar(self, calendar_id: str) -> Dict[str, Any]:
        """
        Remove a non-primary Outlook calendar and all its events.

        Args:
            calendar_id (str): The calendar to remove.

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

    def schedule_event(
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
        Schedule a NEW event on an Outlook calendar. Always allocates a
        fresh event_id; cannot be used to modify an existing event. To
        add attendees to an existing event, use invite_to_event (single
        email) or modify_event(attendees=[...]) (replace whole list).

        Args:
            calendar_id (str): The calendar.
            title (str): Event title.
            start_time (str): Start time (ISO-8601).
            end_time (str): End time (ISO-8601).
            description (str, optional): Event description.
            location (str, optional): Location.
            attendees (List[Dict], optional): Initial attendee list for the
                new event, each with email (str), name (str, optional).
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

    def modify_event(
        self, event_id: str,
        title: Optional[str] = None, start_time: Optional[str] = None,
        end_time: Optional[str] = None, description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[Dict[str, Any]]] = None,
        reminders: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Modify an event's properties.

        Args:
            event_id (str): The event to modify.
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
            Dict[str, Any]: Modified event object.
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

    def get_event_details(self, event_id: str) -> Dict[str, Any]:
        """
        Get full event details.

        Args:
            event_id (str): The event.

        Returns:
            Dict[str, Any]: Full event object.
        """
        return deepcopy(self._require_event(event_id))

    def get_events(
        self, calendar_id: Optional[str] = None,
        start_date: Optional[str] = None, end_date: Optional[str] = None,
        max_results: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get events, optionally filtered by calendar and date range.

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

    def find_events(
        self, query: str, calendar_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find events by text query across title, description, and location.

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

    def respond_to_event(self, event_id: str, response: str) -> Dict[str, Any]:
        """
        Respond to an event invitation.

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

    def invite_to_event(
        self, event_id: str, email: str, name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Invite an attendee to an event.

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

    def uninvite_from_event(self, event_id: str, email: str) -> Dict[str, Any]:
        """
        Uninvite an attendee from an event.

        Args:
            event_id (str): The event.
            email (str): Attendee's email to uninvite.

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
    # Working Hours (Outlook-exclusive)
    # -----------------------------------------------------------------------

    def configure_working_hours(self, days: List[str], start_time: str,
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

    def list_event_categories(self) -> List[Dict[str, Any]]:
        """
        List available event categories.

        Returns:
            List[Dict[str, Any]]: Categories with name and color.
        """
        return deepcopy(self.categories)

    # -----------------------------------------------------------------------
    # Scheduling Poll / FindTime (Outlook-exclusive)
    # -----------------------------------------------------------------------

    def create_scheduling_poll(
        self,
        title: str,
        proposed_times: List[Dict[str, str]],
        attendees: List[str],
        duration_minutes: int,
        location: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a scheduling poll (FindTime).  Propose multiple time slots
        and let attendees vote on their preferred times.

        Args:
            title (str): Title of the meeting to schedule.
            proposed_times (List[Dict[str, str]]): Proposed time options, each
                with start_time (str) and end_time (str) in ISO-8601.
            attendees (List[str]): List of attendee email addresses.
            duration_minutes (int): Duration of the meeting in minutes.
            location (str, optional): Meeting location.

        Returns:
            Dict[str, Any]: Poll object with poll_id, title, status, slots,
                attendees, location, duration_minutes, created_at.
        """
        if not title:
            raise OutlookCalendarError("EMPTY_TITLE", "Poll title cannot be empty.")
        if not proposed_times:
            raise OutlookCalendarError("NO_PROPOSED_TIMES",
                                        "At least one proposed time is required.")
        if not attendees:
            raise OutlookCalendarError("NO_ATTENDEES",
                                        "At least one attendee is required.")

        poll_id = self._new_id("poll")
        slots = []
        for i, pt in enumerate(proposed_times):
            slots.append({
                "slot_id": f"{poll_id}_slot_{i + 1}",
                "start_time": pt.get("start_time", ""),
                "end_time": pt.get("end_time", ""),
                "votes": [],
            })

        poll = {
            "poll_id": poll_id,
            "title": title,
            "status": "open",
            "slots": slots,
            "attendees": attendees,
            "location": location,
            "duration_minutes": duration_minutes,
            "created_at": _utc_now_iso(),
        }
        self.scheduling_polls[poll_id] = poll
        return deepcopy(poll)

    def get_scheduling_poll(self, poll_id: str) -> Dict[str, Any]:
        """
        View a scheduling poll with responses and the current leading time.

        Args:
            poll_id (str): The poll to retrieve.

        Returns:
            Dict[str, Any]: Poll object with poll_id, title, status, slots
                (each with votes), attendees, location, duration_minutes,
                leading_slot, created_at.
        """
        poll = self.scheduling_polls.get(poll_id)
        if not poll:
            raise OutlookCalendarError("POLL_NOT_FOUND",
                                        f"Scheduling poll '{poll_id}' not found.",
                                        suggested_action="Use create_scheduling_poll().")

        result = deepcopy(poll)

        # Determine leading slot (most "yes" votes)
        best_slot = None
        best_yes = -1
        for slot in result.get("slots", []):
            yes_count = sum(1 for v in slot.get("votes", []) if v.get("response") == "yes")
            if yes_count > best_yes:
                best_yes = yes_count
                best_slot = slot.get("slot_id")
        result["leading_slot"] = best_slot
        return result

    def vote_on_poll(
        self,
        poll_id: str,
        votes: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """
        Cast votes on a scheduling poll.

        Args:
            poll_id (str): The poll to vote on.
            votes (List[Dict[str, str]]): List of votes, each with slot_id
                (str) and response (str — "yes", "maybe", or "no").

        Returns:
            Dict[str, Any]: poll_id, votes_cast (int), status "voted".
        """
        poll = self.scheduling_polls.get(poll_id)
        if not poll:
            raise OutlookCalendarError("POLL_NOT_FOUND",
                                        f"Scheduling poll '{poll_id}' not found.")
        if poll.get("status") != "open":
            raise OutlookCalendarError("POLL_CLOSED",
                                        "This poll is no longer open for voting.")

        voter_email = self.profile.get("email", "")
        slot_map = {s["slot_id"]: s for s in poll.get("slots", [])}
        votes_cast = 0

        for vote in votes:
            sid = vote.get("slot_id", "")
            response = vote.get("response", "")
            if response not in ("yes", "maybe", "no"):
                raise OutlookCalendarError("INVALID_VOTE",
                                            f"Vote response must be 'yes', 'maybe', or 'no', got '{response}'.")
            slot = slot_map.get(sid)
            if not slot:
                raise OutlookCalendarError("SLOT_NOT_FOUND",
                                            f"Slot '{sid}' not found in poll '{poll_id}'.")
            # Remove any previous vote from this voter
            slot["votes"] = [v for v in slot.get("votes", []) if v.get("email") != voter_email]
            slot["votes"].append({"email": voter_email, "response": response})
            votes_cast += 1

        return {"poll_id": poll_id, "votes_cast": votes_cast, "status": "voted"}

    def finalize_poll(self, poll_id: str) -> Dict[str, Any]:
        """
        Finalize a scheduling poll.  Picks the winning time slot (most "yes"
        votes) and creates a calendar event.

        Args:
            poll_id (str): The poll to finalize.

        Returns:
            Dict[str, Any]: poll_id, event_id, winning_slot, status
                "finalized".
        """
        poll = self.scheduling_polls.get(poll_id)
        if not poll:
            raise OutlookCalendarError("POLL_NOT_FOUND",
                                        f"Scheduling poll '{poll_id}' not found.")
        if poll.get("status") != "open":
            raise OutlookCalendarError("POLL_ALREADY_FINALIZED",
                                        "This poll has already been finalized.")

        # Find slot with most "yes" votes
        best_slot = None
        best_yes = -1
        for slot in poll.get("slots", []):
            yes_count = sum(1 for v in slot.get("votes", []) if v.get("response") == "yes")
            if yes_count > best_yes:
                best_yes = yes_count
                best_slot = slot

        if not best_slot:
            raise OutlookCalendarError("NO_SLOTS", "Poll has no slots to finalize.")

        # Find the primary calendar
        primary_cal = None
        for cal in self.calendars.values():
            if cal.get("is_primary"):
                primary_cal = cal["calendar_id"]
                break
        if not primary_cal:
            primary_cal = next(iter(self.calendars), None)
        if not primary_cal:
            raise OutlookCalendarError("NO_CALENDAR",
                                        "No calendar available to create the event.")

        attendee_list = [{"email": e} for e in poll.get("attendees", [])]
        event = self.schedule_event(
            calendar_id=primary_cal,
            title=poll["title"],
            start_time=best_slot["start_time"],
            end_time=best_slot["end_time"],
            location=poll.get("location"),
            attendees=attendee_list,
        )

        poll["status"] = "finalized"
        poll["winning_slot"] = best_slot["slot_id"]
        poll["event_id"] = event["event_id"]

        return {
            "poll_id": poll_id,
            "event_id": event["event_id"],
            "winning_slot": best_slot["slot_id"],
            "status": "finalized",
        }

    # -----------------------------------------------------------------------
    # Room & Resource Booking (Outlook-exclusive, new)
    # -----------------------------------------------------------------------

    def list_rooms(self, building: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List available meeting rooms with capacity and equipment.

        Args:
            building (str, optional): Filter rooms by building name.

        Returns:
            List[Dict[str, Any]]: Room objects with room_id, name, capacity,
                building, floor, equipment.
        """
        results = []
        for room in self.rooms.values():
            if building and room.get("building", "") != building:
                continue
            results.append(deepcopy(room))
        return results

    def check_room_availability(
        self,
        room_id: str,
        start_time: str,
        end_time: str,
    ) -> Dict[str, Any]:
        """
        Check if a meeting room is available during a time range.

        Args:
            room_id (str): The room to check.
            start_time (str): Start of range (ISO-8601).
            end_time (str): End of range (ISO-8601).

        Returns:
            Dict[str, Any]: room_id, available (bool), conflicting_events
                (List of event_ids if busy).
        """
        room = self.rooms.get(room_id)
        if not room:
            raise OutlookCalendarError("ROOM_NOT_FOUND",
                                        f"Room '{room_id}' not found.",
                                        suggested_action="Use list_rooms().")

        conflicts = []
        for ev in self.events.values():
            if ev.get("status") == "cancelled":
                continue
            if ev.get("room_id") != room_id:
                continue
            if ev.get("end_time", "") <= start_time:
                continue
            if ev.get("start_time", "") >= end_time:
                continue
            conflicts.append(ev["event_id"])

        return {
            "room_id": room_id,
            "available": len(conflicts) == 0,
            "conflicting_events": conflicts,
        }

    def book_room(self, event_id: str, room_id: str) -> Dict[str, Any]:
        """
        Attach a room reservation to an existing event.  Validates the room
        is free during the event's time range.

        Args:
            event_id (str): The event to attach the room to.
            room_id (str): The room to book.

        Returns:
            Dict[str, Any]: room_id, event_id, room_name, status "booked".
        """
        ev = self._require_event(event_id)
        room = self.rooms.get(room_id)
        if not room:
            raise OutlookCalendarError("ROOM_NOT_FOUND",
                                        f"Room '{room_id}' not found.",
                                        suggested_action="Use list_rooms().")

        # Check availability
        avail = self.check_room_availability(
            room_id, ev.get("start_time", ""), ev.get("end_time", ""))
        # Exclude current event from conflict check
        conflicts = [c for c in avail.get("conflicting_events", []) if c != event_id]
        if conflicts:
            raise OutlookCalendarError("ROOM_BUSY",
                                        f"Room '{room_id}' is not available during this time.",
                                        context={"conflicting_events": conflicts})

        ev["location"] = room.get("name", room_id)
        ev["room_id"] = room_id
        ev["updated_at"] = _utc_now_iso()
        return {
            "room_id": room_id,
            "event_id": event_id,
            "room_name": room.get("name"),
            "status": "booked",
        }

    def release_room(self, event_id: str) -> Dict[str, Any]:
        """
        Release a room booking from an event.

        Args:
            event_id (str): The event to release the room from.

        Returns:
            Dict[str, Any]: event_id, room_id, status "released".
        """
        ev = self._require_event(event_id)
        room_id = ev.get("room_id")
        if not room_id:
            raise OutlookCalendarError("NO_ROOM_BOOKED",
                                        f"Event '{event_id}' does not have a room booking.")
        ev.pop("room_id", None)
        ev["location"] = None
        ev["updated_at"] = _utc_now_iso()
        return {"event_id": event_id, "room_id": room_id, "status": "released"}
