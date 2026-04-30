"""Runtime patches for GoogleCalendarAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.google_calendar import GoogleCalendarAPI, GoogleCalendarError
from datetime import datetime
from datetime import datetime, timezone
import types
import uuid

# ─── Source: jason ────────────────────────────────────────────────────────────


@GoogleCalendarAPI._register_patch("get_free_busy", "availability_engine_offline")
def get_free_busy_availability_engine_offline(self, time_min, time_max):
    raise GoogleCalendarError(
        error_code="AVAILABILITY_ENGINE_OFFLINE",
        message="",
        suggested_action="",
        context={},
    )


@GoogleCalendarAPI._register_patch("create_event", "write_throttled")
def create_event_write_throttled(self, calendar_id, title, start_time, end_time, **kwargs):
    if self._patch_call_count == 2:
        raise GoogleCalendarError(
            error_code="WRITE_THROTTLED",
            message="Write operations are temporarily throttled. Please retry after a brief wait.",
            suggested_action="Wait a few seconds and retry the create_event call.",
            context={"retry_after_seconds": 5},
        )
    return self._original_function(calendar_id, title, start_time, end_time, **kwargs)


@GoogleCalendarAPI._register_patch("share_calendar", "sharing_blocked_by_policy")
def share_calendar_sharing_blocked_by_policy(self, calendar_id, email, role="reader"):
    raise GoogleCalendarError(
        error_code="SHARING_BLOCKED_BY_POLICY",
        message="Calendar sharing is blocked by your organization's admin policy.",
        suggested_action="Contact your IT administrator to enable calendar sharing, or use Outlook Calendar as an alternative.",
        context={"policy": "org_admin_restriction"},
    )


@GoogleCalendarAPI._register_patch("get_free_busy", "stale_free_busy_index")
def get_free_busy_stale_free_busy_index(self, time_min, time_max):
    return {"time_min": time_min, "time_max": time_max, "busy": []}


# ft_extra_75 -- data_staleness/temporary. First call returns an empty
# free/busy view (mirroring a stale availability cache); second call
# falls through to the live implementation and surfaces real conflicts.
# Used to test that the agent retries before committing to a downstream
# booking that depends on availability.
@GoogleCalendarAPI._register_patch("get_free_busy", "stale_snapshot_then_live_temporary")
def get_free_busy_stale_snapshot_then_live_temporary(self, time_min, time_max):
    if self._patch_call_count <= 1:
        return {"time_min": time_min, "time_max": time_max, "busy": []}
    return self._original_function(time_min, time_max)


@GoogleCalendarAPI._register_patch("list_events", "stale_search_index")
def list_events_stale_search_index(self, calendar_id=None, time_min=None, time_max=None, max_results=20):
    result = self._original_function(calendar_id, time_min, time_max, max_results)
    if self._patch_call_count == 1:
        for ev in result:
            if "1:1" in ev.get("title", "") and "Lisa" in ev.get("title", ""):
                ev["start_time"] = ev["start_time"].replace("T11:", "T10:")
                ev["end_time"] = ev["end_time"].replace("T11:30", "T10:30")
    return result


@GoogleCalendarAPI._register_patch("search_events", "stale_search_index_phantom")
def search_events_stale_search_index_phantom(self, query, calendar_id=None):
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


@GoogleCalendarAPI._register_patch("add_attendee", "silent_write_conflict")
def add_attendee_silent_write_conflict(self, event_id, email, name=None):
    if self._patch_call_count == 2:
        return {"event_id": event_id, "email": email, "status": "added"}
    return self._original_function(event_id, email, name)


@GoogleCalendarAPI._register_patch("move_event", "silent_move_noop")
def move_event_silent_move_noop(self, event_id, new_calendar_id):
    return {"event_id": event_id, "calendar_id": new_calendar_id, "status": "moved"}


@GoogleCalendarAPI._register_patch("rsvp_event", "silent_rsvp_drop")
def rsvp_event_silent_rsvp_drop(self, event_id, response):
    if self._patch_call_count == 1:
        return {"event_id": event_id, "response": response, "status": "updated"}
    return self._original_function(event_id, response)


@GoogleCalendarAPI._register_patch("share_calendar", "silent_share_noop")
def share_calendar_silent_share_noop(self, calendar_id, email, role="reader"):
    return {"calendar_id": calendar_id, "email": email, "role": role, "status": "shared"}


@GoogleCalendarAPI._register_patch("add_attendee", "event_version_conflict")
def add_attendee_event_version_conflict(self, event_id, email, name=None):
    if self._patch_call_count == 1:
        raise GoogleCalendarError(
            error_code="EVENT_VERSION_CONFLICT",
            message="The event was modified by another user since your last read. Re-fetch and retry.",
            suggested_action="Call get_event() to fetch the latest version, then retry add_attendee().",
            context={"event_id": event_id},
        )
    return self._original_function(event_id, email, name)


@GoogleCalendarAPI._register_patch("update_event", "sync_rule_override")
def update_event_sync_rule_override(self, event_id, title=None, start_time=None, end_time=None,
                     description=None, location=None, attendees=None, reminders=None):
    result = self._original_function(event_id, title, start_time, end_time,
                                     description, location, attendees, reminders)
    ev = self.events.get(event_id)
    if ev:
        ev["start_time"] = "2026-03-20T09:00:00"
        ev["end_time"] = "2026-03-20T09:30:00"
        ev["location"] = "Room A"
    return result


@GoogleCalendarAPI._register_patch("create_event", "time_slot_conflict")
def create_event_time_slot_conflict(self, calendar_id, title, start_time, end_time, **kwargs):
    if self._patch_call_count == 1:
        raise GoogleCalendarError(
            error_code="TIME_SLOT_CONFLICT",
            message="Time slot is still occupied by a recently-deleted event. Try again shortly.",
            suggested_action="Wait a moment for the deletion to propagate, then retry create_event().",
            context={"start_time": start_time, "end_time": end_time},
        )
    return self._original_function(calendar_id, title, start_time, end_time, **kwargs)


@GoogleCalendarAPI._register_patch("get_event", "event_not_found")
def get_event_event_not_found(self, event_id):
    if "weekly_sync" in event_id.lower() or "phantom" in event_id.lower():
        raise GoogleCalendarError(
            error_code="EVENT_NOT_FOUND",
            message=f"Event '{event_id}' not found. It may have been corrupted by a recent calendar deletion.",
            suggested_action="The event may need to be recreated manually.",
            context={"event_id": event_id},
        )
    return self._original_function(event_id)


@GoogleCalendarAPI._register_patch("create_event", "invalid_attendee_format")
def create_event_invalid_attendee_format(self, calendar_id, title, start_time, end_time, **kwargs):
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


@GoogleCalendarAPI._register_patch("quick_add_event", "ambiguous_time_expression")
def quick_add_event_ambiguous_time_expression(self, calendar_id, text):
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
        raise GoogleCalendarError("SERVICE_UNAVAILABLE", "")
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
    Returns success with attendees listed. The first get_event sees the delayed
    empty attendee list; the second get_event restores the attendees."""
    if self._patch_call_count <= 1:
        result = self._original_function(*args, **kwargs)
        event_id = result.get("event_id")
        if event_id and event_id in self.events:
            delayed_attendees = self.events[event_id].get("attendees", [])
            self.events[event_id]["attendees"] = []
            if not hasattr(self, "_attendee_delay_pending"):
                self._attendee_delay_pending = {}
                self._attendee_delay_get_counts = {}
                original_get_event = self.get_event

                def delayed_get_event(bound_self, delayed_event_id):
                    if delayed_event_id in bound_self._attendee_delay_pending:
                        bound_self._attendee_delay_get_counts[delayed_event_id] = (
                            bound_self._attendee_delay_get_counts.get(delayed_event_id, 0) + 1
                        )
                        if bound_self._attendee_delay_get_counts[delayed_event_id] >= 2:
                            bound_self.events[delayed_event_id]["attendees"] = (
                                bound_self._attendee_delay_pending.pop(delayed_event_id)
                            )
                    return original_get_event(delayed_event_id)

                self.get_event = types.MethodType(delayed_get_event, self)
            self._attendee_delay_pending[event_id] = delayed_attendees
            self._attendee_delay_get_counts[event_id] = 0
        return result
    return self._original_function(*args, **kwargs)


# ─── Source: yash ─────────────────────────────────────────────────────────────


# ft_023 -- AM/PM flip (event scheduled at 2-3 AM instead of requested time)
@GoogleCalendarAPI._register_patch("create_event", "ampmflip")
def create_event_ampmflip(self, *args, **kwargs):
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
def quick_add_event_blocked(self, *args, **kwargs):
    raise GoogleCalendarError("FEATURE_DISABLED", "")


# ft_023 -- blocked
@GoogleCalendarAPI._register_patch("list_events", "blocked")
def list_events_blocked(self, *args, **kwargs):
    raise GoogleCalendarError("FEATURE_DISABLED", "")


# ft_023 -- blocked
@GoogleCalendarAPI._register_patch("search_events", "blocked")
def search_events_blocked(self, *args, **kwargs):
    raise GoogleCalendarError("FEATURE_DISABLED", "")


# ft_023 -- blocked
@GoogleCalendarAPI._register_patch("update_event", "blocked")
def update_event_blocked(self, *args, **kwargs):
    raise GoogleCalendarError("FEATURE_DISABLED", "")


# ---------- create_event (attendee_role_required_permanent) ----------


# ft_extra_46 -- schema_mismatch/permanent. The Google Calendar attendee
# schema has been migrated to require an explicit 'role' field on every
# attendee entry (one of "required", "optional", "resource"). Until the
# client SDK is updated, attempts to create an event with the legacy
# string-only attendee list permanently fail. Suggested action steers
# the agent toward the Outlook calendar fallback rather than retrying.
@GoogleCalendarAPI._register_patch("create_event", "attendee_role_required_permanent")
def create_event_attendee_role_required_permanent(self, *args, **kwargs):
    """Permanent. Always raises ATTENDEE_ROLE_REQUIRED. Agent should
    pivot to OutlookCalendarAPI.schedule_event or warn the user."""
    raise GoogleCalendarError(
        "ATTENDEE_ROLE_REQUIRED",
        (
            "create_event rejected: the new attendee schema requires an "
            "explicit 'role' field (required|optional|resource) on each "
            "attendee. Legacy email-only attendee strings are no longer "
            "accepted."
        ),
        (
            "Do NOT retry with the same payload -- the rollout is "
            "permanent. Pivot to OutlookCalendarAPI.schedule_event for "
            "this attendee set, or warn the user."
        ),
    )


# ft_247 -- silent_noop/temporary. update_event acknowledges a location
# change in the response payload but does not persist the new location
# on the stored event. All other fields update normally. Second call
# (after the agent verifies via get_event and detects the unchanged
# location) writes through. Models that book downstream transport
# without verifying will route to the stale address.
@GoogleCalendarAPI._register_patch("update_event", "location_silent_drop_temporary")
def update_event_location_silent_drop_temporary(
    self,
    event_id,
    title=None,
    start_time=None,
    end_time=None,
    description=None,
    location=None,
    attendees=None,
    reminders=None,
):
    """Temporary silent no-op on the location field only. First call:
    update lands for every field except location -- the response includes
    the requested location but the stored event keeps its old one. Second
    call falls through to the original function so the location actually
    persists."""
    if self._patch_call_count <= 1 and location is not None:
        ev = self._require_event(event_id)
        old_location = ev.get("location")
        result = self._original_function(
            event_id, title, start_time, end_time, description,
            None,  # do NOT actually overwrite location on disk
            attendees, reminders,
        )
        # Restore old location on the stored event (defensive, in case
        # _original_function ever changes signature semantics).
        ev["location"] = old_location
        # But pretend in the response payload that the new location took.
        result["location"] = location
        return result
    return self._original_function(
        event_id, title, start_time, end_time, description,
        location, attendees, reminders,
    )


# ft_extra_40 -- silent_noop/temporary. update_event with a non-None
# reminders payload acknowledges the change in the response but does
# NOT persist the new reminders on the stored event. All other fields
# update normally. Second call (after the agent verifies via get_event
# and detects the unchanged reminders) writes through. This is the
# canonical "reminder set silently dropped" failure -- migrated from
# the deleted set_event_reminder method during the Round-2 source
# cleanup that consolidated reminder writes into update_event.
@GoogleCalendarAPI._register_patch("update_event", "silent_reminder_drop_temporary")
def update_event_silent_reminder_drop_temporary(
    self,
    event_id,
    title=None,
    start_time=None,
    end_time=None,
    description=None,
    location=None,
    attendees=None,
    reminders=None,
):
    """Temporary silent no-op on the reminders field only. First call:
    update lands for every field except reminders -- the response includes
    the requested reminders but the stored event keeps its old list. Second
    call falls through to the original function so the reminders actually
    persist."""
    if self._patch_call_count <= 1 and reminders is not None:
        ev = self._require_event(event_id)
        old_reminders = list(ev.get("reminders", []))
        result = self._original_function(
            event_id, title, start_time, end_time, description,
            location, attendees,
            None,  # do NOT actually overwrite reminders on disk
        )
        # Restore old reminders on the stored event (defensive).
        ev["reminders"] = old_reminders
        # Pretend in the response payload that the new reminders took.
        result["reminders"] = reminders
        return result
    return self._original_function(
        event_id, title, start_time, end_time, description,
        location, attendees, reminders,
    )


# ─── Source: yash (alternate-path blockers) ───


@GoogleCalendarAPI._register_patch("book_appointment_slot", "blocked")
def book_appointment_slot_blocked(self, *args, **kwargs):
    raise GoogleCalendarError("FEATURE_DISABLED", "")
