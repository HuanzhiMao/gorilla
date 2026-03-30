"""Runtime patches for OutlookCalendarAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.outlook_calendar import OutlookCalendarAPI, OutlookCalendarError

# ============================================================================
# S28: Outlook Calendar cancel_event permanently returns deprecation error
# Trigger: cancel_event always raises API_VERSION_DEPRECATED
# ============================================================================
@OutlookCalendarAPI._register_patch("cancel_event", "api_version_deprecated")
def cancel_event_api_version_deprecated(self, event_id):
    raise OutlookCalendarError(
        error_code="API_VERSION_DEPRECATED",
        message="The cancel_event endpoint has been deprecated in this API version.",
        suggested_action="Use modify_event() to set the event status to 'cancelled' as a workaround, or use Google Calendar's delete_event().",
        context={"event_id": event_id},
    )


# ============================================================================
# S29: Outlook Calendar find_meeting_times transiently fails (Graph API timeout)
# Trigger: find_meeting_times raises GRAPH_AVAILABILITY_TIMEOUT on 1st call;
#          retry succeeds
# ============================================================================
@OutlookCalendarAPI._register_patch("find_meeting_times", "graph_availability_timeout")
def find_meeting_times_graph_availability_timeout(self, attendee_emails, duration_minutes, time_min, time_max):
    if self._patch_call_count == 1:
        raise OutlookCalendarError(
            error_code="GRAPH_AVAILABILITY_TIMEOUT",
            message="Microsoft Graph availability service timed out. The request may succeed on retry.",
            suggested_action="Retry the request after a brief wait.",
            context={"retry_after_seconds": 10},
        )
    return self._original_function(attendee_emails, duration_minutes, time_min, time_max)


# ============================================================================
# S32: Outlook Calendar room availability index permanently stale;
#      all room bookings fail with ROOM_ALREADY_BOOKED
# Trigger: book_room always raises ROOM_ALREADY_BOOKED
# ============================================================================
@OutlookCalendarAPI._register_patch("book_room", "room_already_booked")
def book_room_room_already_booked(self, room_id, event_id):
    raise OutlookCalendarError(
        error_code="ROOM_ALREADY_BOOKED",
        message="The requested conference room is already booked for this time slot.",
        suggested_action="Try a different room, a different time slot, or set the location manually via modify_event().",
        context={"room_id": room_id},
    )


# ============================================================================
# S33: Outlook Calendar get_schedule returns stale materialized view
#      missing recently-created events
# Trigger: get_schedule returns incomplete data (missing 2 events)
# ============================================================================
@OutlookCalendarAPI._register_patch("get_schedule", "stale_materialized_view")
def get_schedule_stale_materialized_view(self, start_date, end_date):
    result = self._original_function(start_date, end_date)
    schedule = result.get("schedule", [])
    if len(schedule) > 2:
        result["schedule"] = schedule[:len(schedule) - 2]
        result["_materialized_at"] = "2026-03-19T06:00:00Z"
    return result


# ============================================================================
# S38: Outlook Calendar set_category silently doesn't persist category tags
# Trigger: set_category returns success but doesn't add the category to the event
# ============================================================================
@OutlookCalendarAPI._register_patch("set_category", "silent_category_noop")
def set_category_silent_category_noop(self, event_id, category):
    return {"event_id": event_id, "category": category, "status": "tagged"}


# ============================================================================
# S44: Outlook Calendar create_event returns temporary internal event_id
#      that differs from permanent one; subsequent add_attendee fails
# Trigger: add_attendee raises EVENT_NOT_FOUND on 1st call (wrong ID);
#          agent discovers correct ID via list_events; retry works
# ============================================================================
@OutlookCalendarAPI._register_patch("invite_to_event", "event_not_found")
def invite_to_event_event_not_found(self, event_id, email, name=None):
    if self._patch_call_count == 1:
        raise OutlookCalendarError(
            error_code="EVENT_NOT_FOUND",
            message=f"Event '{event_id}' not found. The event ID may have been reassigned after creation.",
            suggested_action="Use get_events() to find the event by title and date, then use the correct event_id.",
            context={"event_id": event_id},
        )
    return self._original_function(event_id, email, name)


# ============================================================================
# S46: Outlook Calendar book_room requires undocumented fields
# Trigger: book_room raises cascading MISSING_REQUIRED_FIELD errors
# ============================================================================
@OutlookCalendarAPI._register_patch("book_room", "missing_required_field")
def book_room_missing_required_field(self, room_id, event_id):
    if self._patch_call_count == 1:
        raise OutlookCalendarError(
            error_code="MISSING_REQUIRED_FIELD",
            message="Required field 'room_resource_id' format is invalid. Use the full resource URI.",
            suggested_action="Use the room's full resource URI from list_rooms().",
            context={"missing_field": "room_resource_uri"},
        )
    elif self._patch_call_count == 2:
        raise OutlookCalendarError(
            error_code="MISSING_REQUIRED_FIELD",
            message="Required field 'booking_type' is missing. Must be 'standard' or 'recurring'.",
            suggested_action="Include booking_type='standard' parameter.",
            context={"missing_field": "booking_type"},
        )
    raise OutlookCalendarError(
        error_code="INTERNAL_SCHEMA_ERROR",
        message="The room booking endpoint is experiencing persistent schema incompatibility.",
        suggested_action="Room booking is currently unavailable. Set the event location manually via modify_event().",
        context={},
    )


# ============================================================================
# S47: Outlook Calendar set_working_hours rejects day format
# Trigger: set_working_hours raises cascading INVALID_DAY_FORMAT errors
# ============================================================================
@OutlookCalendarAPI._register_patch("set_working_hours", "invalid_day_format")
def set_working_hours_invalid_day_format(self, days, start_time, end_time, timezone):
    if self._patch_call_count == 1:
        raise OutlookCalendarError(
            error_code="INVALID_DAY_FORMAT",
            message="Day names must use abbreviated format ('Mon', 'Tue', ...), not full names.",
            suggested_action="Use 'Mon' instead of 'Monday', 'Tue' instead of 'Tuesday', etc.",
            context={},
        )
    elif self._patch_call_count == 2:
        raise OutlookCalendarError(
            error_code="MISSING_REQUIRED_FIELD",
            message="Required field 'timezone_windows_id' is missing.",
            suggested_action="Include timezone_windows_id='Eastern Standard Time' parameter.",
            context={"missing_field": "timezone_windows_id"},
        )
    raise OutlookCalendarError(
        error_code="INTERNAL_SCHEMA_ERROR",
        message="The working hours endpoint is experiencing persistent schema incompatibility.",
        suggested_action="Set working hours manually in Outlook settings. Proceed with other tasks.",
        context={},
    )


# ============================================================================
# S49: Outlook Calendar create_event rejects ISO-8601 times, requires custom format
# Trigger: create_event raises cascading DATETIME_FORMAT_INVALID errors
# ============================================================================
@OutlookCalendarAPI._register_patch("schedule_event", "datetime_format_invalid")
def schedule_event_datetime_format_invalid(self, calendar_id, title, start_time, end_time, **kwargs):
    if self._patch_call_count == 1:
        raise OutlookCalendarError(
            error_code="DATETIME_FORMAT_INVALID",
            message="ISO-8601 datetime format is not accepted. Use 'MM/DD/YYYY HH:MM AM/PM' format.",
            suggested_action="Use '03/17/2026 12:00 AM' instead of '2026-03-17T00:00:00'.",
            context={},
        )
    elif self._patch_call_count == 2:
        raise OutlookCalendarError(
            error_code="MISSING_REQUIRED_FIELD",
            message="Required field 'timezone_id' is missing when using custom datetime format.",
            suggested_action="Include timezone_id='Eastern Standard Time' parameter.",
            context={"missing_field": "timezone_id"},
        )
    elif self._patch_call_count == 3:
        raise OutlookCalendarError(
            error_code="INVALID_TIMEZONE_FORMAT",
            message="IANA timezone IDs are not accepted. Use Windows timezone IDs.",
            suggested_action="Use 'Eastern Standard Time' instead of 'America/New_York'.",
            context={},
        )
    raise OutlookCalendarError(
        error_code="INTERNAL_SCHEMA_ERROR",
        message="Outlook Calendar event creation is experiencing persistent schema incompatibility.",
        suggested_action="Use Google Calendar as an alternative for event creation.",
        context={},
    )
