"""Runtime patches for SpotifyAPI methods."""

from mfcl_eval.eval_checker.multi_turn_eval.func_source_code.spotify import SpotifyAPI, SpotifyError

# ============================================================================
# S69: TWICE — all Spotify devices offline, NO_ACTIVE_DEVICE
# Trigger: play_track with no device available
# ============================================================================
@SpotifyAPI._register_patch("start_track", "s69_no_active_device")
def start_track_s69_no_active_device(self, track_id, device_id=None):
    if device_id:
        raise SpotifyError(
            error_code="DEVICE_NOT_FOUND",
            message=f"Device '{device_id}' not found.",
            suggested_action="Use get_devices() to list available devices.",
            context={"device_id": device_id},
        )
    raise SpotifyError(
        error_code="NO_ACTIVE_DEVICE",
        message="No active device found. Specify a device_id or transfer playback first.",
        suggested_action="Call get_devices() and transfer_playback().",
        context={"user_id": self.user_id},
    )


# ============================================================================
# S70: Queencard — removed from Spotify catalog
# Trigger: search_tracks returns empty for Queencard
# ============================================================================
@SpotifyAPI._register_patch("search_tracks", "s70_queencard_removed")
def search_tracks_s70_queencard_removed(self, query, limit=10):
    if "queencard" in query.lower():
        return []
    return self._original_function(query, limit)


# ============================================================================
# S72: Wandering Hearth — album shell empty on Spotify
# Trigger: play_context raises EMPTY_CONTEXT for album:alb_wh
# ============================================================================
@SpotifyAPI._register_patch("play_context", "s72_empty_album")
def play_context_s72_empty_album(self, context_uri, offset=0, device_id=None):
    if "alb_wh" in context_uri:
        raise SpotifyError(
            error_code="EMPTY_CONTEXT",
            message="The context contains no tracks.",
            suggested_action="Choose a context with at least one track.",
            context={"context_uri": context_uri},
        )
    return self._original_function(context_uri, offset, device_id)


# ============================================================================
# S75: Friend's apartment — DEVICE_NOT_OWNED / NO_ACTIVE_DEVICE
# Trigger: play_track fails for any device (user has none, friend's not owned)
# ============================================================================
@SpotifyAPI._register_patch("start_track", "s75_device_not_owned")
def start_track_s75_device_not_owned(self, track_id, device_id=None):
    if device_id and device_id.startswith("dev_friend"):
        raise SpotifyError(
            error_code="DEVICE_NOT_OWNED",
            message="Device does not belong to this user.",
            suggested_action="Use get_devices() to find your devices.",
            context={"device_id": device_id, "user_id": self.user_id},
        )
    raise SpotifyError(
        error_code="NO_ACTIVE_DEVICE",
        message="No active device found.",
        suggested_action="Call get_devices() and transfer_playback().",
        context={"user_id": self.user_id},
    )
