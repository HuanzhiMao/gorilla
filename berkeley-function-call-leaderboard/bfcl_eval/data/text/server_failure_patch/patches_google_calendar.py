"""Runtime patches for GoogleCalendarAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.google_calendar import GoogleCalendarAPI, GoogleCalendarError
from datetime import datetime
from datetime import datetime, timezone
import uuid

# ─── Source: jason ────────────────────────────────────────────────────────────


@GoogleCalendarAPI._register_patch("get_free_busy", "AVAILABILITY_ENGINE_OFFLINE")
def s25_get_free_busy(self, time_min, time_max):
    raise GoogleCalendarError(
        error_code="AVAILABILITY_ENGINE_OFFLINE",
        message="The availability engine is currently offline for maintenance.",
        suggested_action="Use an alternative calendar service to check availability, or try again later.",
        context={},
    )


@GoogleCalendarAPI._register_patch("create_event", "WRITE_THROTTLED")
def s26_create_event(self, calendar_id, title, start_time, end_time, **kwargs):
    if self._patch_call_count == 2:
        raise GoogleCalendarError(
            error_code="WRITE_THROTTLED",
            message="Write operations are temporarily throttled. Please retry after a brief wait.",
            suggested_action="Wait a few seconds and retry the create_event call.",
            context={"retry_after_seconds": 5},
        )
    return self._original_function(calendar_id, title, start_time, end_time, **kwargs)


@GoogleCalendarAPI._register_patch("share_calendar", "SHARING_BLOCKED_BY_POLICY")
def s27_share_calendar(self, calendar_id, email, role="reader"):
    raise GoogleCalendarError(
        error_code="SHARING_BLOCKED_BY_POLICY",
        message="Calendar sharing is blocked by your organization's admin policy.",
        suggested_action="Contact your IT administrator to enable calendar sharing, or use Outlook Calendar as an alternative.",
        context={"policy": "org_admin_restriction"},
    )


@GoogleCalendarAPI._register_patch("get_free_busy", "STALE_FREE_BUSY_INDEX")
def s30_get_free_busy(self, time_min, time_max):
    return {"time_min": time_min, "time_max": time_max, "busy": []}


@GoogleCalendarAPI._register_patch("list_events", "STALE_SEARCH_INDEX")
def s31_list_events(self, calendar_id=None, time_min=None, time_max=None, max_results=20):
    result = self._original_function(calendar_id, time_min, time_max, max_results)
    if self._patch_call_count == 1:
        for ev in result:
            if "1:1" in ev.get("title", "") and "Lisa" in ev.get("title", ""):
                ev["start_time"] = ev["start_time"].replace("T11:", "T10:")
                ev["end_time"] = ev["end_time"].replace("T11:30", "T10:30")
    return result


@GoogleCalendarAPI._register_patch("search_events", "STALE_SEARCH_INDEX_PHANTOM")
def s34_search_events(self, query, calendar_id=None):
    result = self._original_function(query, calendar_id)
    if "project alpha" in query.lower() or "alpha" in query.lower():
        result.insert(0, {
            "event_id": "evt_phantom_kickoff",
            "calendar_id": "cal_primary",
            "title": "Project Alpha Kickoff",
            "description": "Initial kickoff meeting",
            "start_time": "2026-03-01T10:00:00",
            "end_time": "2026-03-01T11:00:00",
            "status": "confirmed",
        })
        result.insert(1, {
            "event_id": "evt_phantom_review",
            "calendar_id": "cal_primary",
            "title": "Project Alpha Review",
            "description": "Mid-cycle review",
            "start_time": "2026-03-05T14:00:00",
            "end_time": "2026-03-05T15:00:00",
            "status": "confirmed",
        })
    return result


@GoogleCalendarAPI._register_patch("add_attendee", "SILENT_WRITE_CONFLICT")
def s35_add_attendee(self, event_id, email, name=None):
    if self._patch_call_count == 2:
        return {"event_id": event_id, "email": email, "status": "added"}
    return self._original_function(event_id, email, name)


@GoogleCalendarAPI._register_patch("move_event", "SILENT_MOVE_NOOP")
def s36_move_event(self, event_id, new_calendar_id):
    return {"event_id": event_id, "calendar_id": new_calendar_id, "status": "moved"}


@GoogleCalendarAPI._register_patch("rsvp_event", "SILENT_RSVP_DROP")
def s37_rsvp_event(self, event_id, response):
    if self._patch_call_count == 1:
        return {"event_id": event_id, "response": response, "status": "updated"}
    return self._original_function(event_id, response)


@GoogleCalendarAPI._register_patch("share_calendar", "SILENT_SHARE_NOOP")
def s39_share_calendar(self, calendar_id, email, role="reader"):
    return {"calendar_id": calendar_id, "email": email, "role": role, "status": "shared"}


@GoogleCalendarAPI._register_patch("add_attendee", "EVENT_VERSION_CONFLICT")
def s40_add_attendee(self, event_id, email, name=None):
    if self._patch_call_count == 1:
        raise GoogleCalendarError(
            error_code="EVENT_VERSION_CONFLICT",
            message="The event was modified by another user since your last read. Re-fetch and retry.",
            suggested_action="Call get_event() to fetch the latest version, then retry add_attendee().",
            context={"event_id": event_id},
        )
    return self._original_function(event_id, email, name)


@GoogleCalendarAPI._register_patch("update_event", "SYNC_RULE_OVERRIDE")
def s41_update_event(self, event_id, title=None, start_time=None, end_time=None,
                     description=None, location=None, attendees=None, reminders=None):
    result = self._original_function(event_id, title, start_time, end_time,
                                     description, location, attendees, reminders)
    ev = self.events.get(event_id)
    if ev:
        ev["start_time"] = "2026-03-20T09:00:00"
        ev["end_time"] = "2026-03-20T09:30:00"
        ev["location"] = "Room A"
    return result


@GoogleCalendarAPI._register_patch("create_event", "TIME_SLOT_CONFLICT")
def s42_create_event(self, calendar_id, title, start_time, end_time, **kwargs):
    if self._patch_call_count == 1:
        raise GoogleCalendarError(
            error_code="TIME_SLOT_CONFLICT",
            message="Time slot is still occupied by a recently-deleted event. Try again shortly.",
            suggested_action="Wait a moment for the deletion to propagate, then retry create_event().",
            context={"start_time": start_time, "end_time": end_time},
        )
    return self._original_function(calendar_id, title, start_time, end_time, **kwargs)


@GoogleCalendarAPI._register_patch("get_event", "EVENT_NOT_FOUND")
def s43_get_event(self, event_id):
    if "weekly_sync" in event_id.lower() or "phantom" in event_id.lower():
        raise GoogleCalendarError(
            error_code="EVENT_NOT_FOUND",
            message=f"Event '{event_id}' not found. It may have been corrupted by a recent calendar deletion.",
            suggested_action="The event may need to be recreated manually.",
            context={"event_id": event_id},
        )
    return self._original_function(event_id)


@GoogleCalendarAPI._register_patch("create_event", "INVALID_ATTENDEE_FORMAT")
def s45_create_event(self, calendar_id, title, start_time, end_time, **kwargs):
    if self._patch_call_count == 1:
        raise GoogleCalendarError(
            error_code="INVALID_ATTENDEE_FORMAT",
            message="Attendees must be objects with 'email' key, not plain strings.",
            suggested_action="Pass attendees as [{\"email\": \"bob@company.com\"}, {\"email\": \"carol@company.com\"}] instead of [\"bob@company.com\", \"carol@company.com\"].",
            context={
                "expected_format": [{"email": "user@example.com"}],
            },
        )
    return self._original_function(calendar_id, title, start_time, end_time, **kwargs)


@GoogleCalendarAPI._register_patch("quick_add_event", "AMBIGUOUS_TIME_EXPRESSION")
def s48_quick_add_event(self, calendar_id, text):
    if self._patch_call_count == 1:
        raise GoogleCalendarError(
            error_code="AMBIGUOUS_TIME_EXPRESSION",
            message="Time expression is ambiguous without an explicit timezone.",
            suggested_action="Include the timezone in the text, e.g., 'tomorrow at noon EST'.",
            context={
                "user_timezone": "America/New_York",
                "original_text": text,
            },
        )
    return self._original_function(calendar_id, text)


# ─── Source: socrates ─────────────────────────────────────────────────────────


@GoogleCalendarAPI._register_patch("create_event", "noop_permanent")
def create_event_noop_permanent(self, *args, **kwargs):
    """Permanent silent no-op. Returns fake event confirmation without ever creating it.
    The event never exists, so get_event will correctly fail."""
    now = datetime.now(timezone.utc).isoformat()
    event_id = f"evt_{uuid.uuid4().hex[:8]}"
    return {
        "event_id": event_id,
        "calendar_id": kwargs.get("calendar_id", "primary"),
        "title": kwargs.get("title", ""),
        "description": kwargs.get("description", ""),
        "start_time": kwargs.get("start_time", ""),
        "end_time": kwargs.get("end_time", ""),
        "all_day": kwargs.get("all_day", False),
        "status": "confirmed",
        "attendees": kwargs.get("attendees", []),
        "reminders": kwargs.get("reminders", []),
        "created_at": now,
        "updated_at": now,
    }


@GoogleCalendarAPI._register_patch("create_event", "unavailable_temporary")
def create_event_unavailable_temporary(self, *args, **kwargs):
    """Temporary. Fails on calls 1-2, passes through on 3+."""
    if self._patch_call_count <= 2:
        raise GoogleCalendarError(
            "SERVICE_UNAVAILABLE",
            "Google Calendar service temporarily unavailable.",
            "Retry the request.",
        )
    return self._original_function(*args, **kwargs)


@GoogleCalendarAPI._register_patch("create_event", "schema_mismatch_permanent")
def create_event_schema_mismatch_permanent(self, *args, **kwargs):
    """Permanent. Always raises SCHEMA_CHANGED about missing timezone param."""
    raise GoogleCalendarError(
        "SCHEMA_CHANGED",
        "The 'timezone' parameter is now required for all event creation. Specify timezone as IANA format (e.g., 'America/Chicago').",
        "Include 'timezone' parameter.",
    )


@GoogleCalendarAPI._register_patch("create_event", "attendee_delay_temporary")
def create_event_attendee_delay_temporary(self, *args, **kwargs):
    """Temporary silent no-op. On first call, creates event but removes attendees from the stored event.
    Returns success with attendees listed. On 2nd+, passes through normally."""
    if self._patch_call_count <= 1:
        result = self._original_function(*args, **kwargs)
        event_id = result.get("event_id")
        if event_id and event_id in self.events:
            # Remove attendees from the stored event (but keep them in the response)
            self.events[event_id]["attendees"] = []
        return result
    return self._original_function(*args, **kwargs)


# ─── Source: yash ─────────────────────────────────────────────────────────────


# ft_023 -- AM/PM flip (event scheduled at 2-3 AM instead of requested time)
@GoogleCalendarAPI._register_patch("create_event", "ampmflip")
def ft023_create_event_ampmflip(self, *args, **kwargs):
    fixed_kwargs = dict(kwargs)
    start_time = fixed_kwargs.get("start_time")
    end_time = fixed_kwargs.get("end_time")
    if start_time and end_time:
        start_dt = datetime.fromisoformat(start_time)
        end_dt = datetime.fromisoformat(end_time)
        fixed_kwargs["start_time"] = start_dt.replace(hour=2, minute=0).isoformat()
        fixed_kwargs["end_time"] = end_dt.replace(hour=3, minute=0).isoformat()
    event = self._original_function(*args, **fixed_kwargs)
    return {"event_id": event["event_id"], "status": event["status"]}


# ft_023 -- blocked
@GoogleCalendarAPI._register_patch("quick_add_event", "blocked")
def ft023_quick_add_event_blocked(self, *args, **kwargs):
    raise GoogleCalendarError(
        "FEATURE_DISABLED",
        "This feature is currently disabled. Try using create_event instead.",
    )


# ft_023 -- blocked
@GoogleCalendarAPI._register_patch("list_events", "blocked")
def ft023_list_events_blocked(self, *args, **kwargs):
    raise GoogleCalendarError(
        "FEATURE_DISABLED",
        "This feature is currently disabled. Try using get_event instead.",
    )


# ft_023 -- blocked
@GoogleCalendarAPI._register_patch("search_events", "blocked")
def ft023_search_events_blocked(self, *args, **kwargs):
    raise GoogleCalendarError(
        "FEATURE_DISABLED",
        "This feature is currently disabled. Try using get_event instead.",
    )


# ft_023 -- blocked
@GoogleCalendarAPI._register_patch("update_event", "blocked")
def ft023_update_event_blocked(self, *args, **kwargs):
    raise GoogleCalendarError(
        "FEATURE_DISABLED",
        "This feature is currently disabled. Try a different approach to modify your event.",
    )
