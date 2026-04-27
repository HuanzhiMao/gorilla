"""Runtime patches for SpotifyAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.spotify import SpotifyAPI, SpotifyError

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


# ---------- fetch_playlist (stale_track_snapshot_temporary) ----------


# ft_extra_38 -- data_staleness/temporary. First call returns the
# playlist with a stale 'tracks' snapshot (the most recently added track
# is missing). Second call falls through to the live snapshot.
@SpotifyAPI._register_patch("fetch_playlist", "stale_track_snapshot_temporary")
def fetch_playlist_stale_track_snapshot_temporary(self, playlist_id, *args, **kwargs):
    """Temporary. First call drops the last entry from the 'tracks' list
    and stamps a 'stale_snapshot' marker. Second call returns the real
    playlist."""
    if self._patch_call_count <= 1:
        result = self._original_function(playlist_id, *args, **kwargs)
        if isinstance(result, dict) and isinstance(result.get("tracks"), list) and result["tracks"]:
            result["tracks"] = result["tracks"][:-1]
            result["stale_snapshot"] = True
        return result
    return self._original_function(playlist_id, *args, **kwargs)


# ---------- start_track (premium_device_required_temporary) ----------


# ft_extra_56 -- availability_denial/temporary. The first call rejects
# with PREMIUM_DEVICE_REQUIRED (a regional Spotify Connect entitlement
# check that briefly returned the wrong answer). The second call falls
# through to the original implementation.
@SpotifyAPI._register_patch("start_track", "premium_device_required_temporary")
def start_track_premium_device_required_temporary(self, track_id, *args, **kwargs):
    """Temporary. First call raises PREMIUM_DEVICE_REQUIRED with a clearly
    retryable hint; second call falls through."""
    if self._patch_call_count <= 1:
        raise SpotifyError(
            error_code="PREMIUM_DEVICE_REQUIRED",
            message=(
                "Spotify Connect briefly reported the active device is "
                "ineligible for premium playback."
            ),
            suggested_action=(
                "Retry once -- the entitlement check is flaky and recovers "
                "within a few seconds."
            ),
            context={"track_id": track_id, "retryable": True},
        )
    return self._original_function(track_id, *args, **kwargs)
