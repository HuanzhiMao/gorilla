"""Runtime patches for AppleMusicAPI methods."""

from bfcl_eval.eval_checker.multi_turn_eval.func_source_code.apple_music import AppleMusicAPI, AppleMusicError

# ─── Source: patches_apple_music.py ───


# ============================================================================
# S66: Phosphor album removed from AM catalog
# Trigger: search_catalog returns empty albums for "Phosphor"
# ============================================================================
@AppleMusicAPI._register_patch("search_catalog", "s66_phosphor_removed")
def search_catalog_s66_phosphor_removed(self, query, types=None, limit=10):
    result = self._original_function(query, types, limit)
    if "phosphor" in query.lower():
        if "albums" in result:
            result["albums"] = []
    return result


# ============================================================================
# S67: Morning Rituals — playlist shell exists, zero tracks
# Trigger: play_playlist raises EMPTY_PLAYLIST for pl_morning
# Note: Can also be done via initial state with track_ids=[]
# ============================================================================
@AppleMusicAPI._register_patch("play_playlist", "s67_empty_playlist")
def play_playlist_s67_empty_playlist(self, playlist_id, track_offset=0):
    if playlist_id == "pl_morning":
        raise AppleMusicError(
            error_code="EMPTY_PLAYLIST",
            message="This playlist has no tracks.",
            suggested_action="Add tracks to the playlist first.",
            context={"playlist_id": playlist_id},
        )
    return self._original_function(playlist_id, track_offset)


# ============================================================================
# S68: Ghost track in playback — rate_track fails
# Trigger: rate_track raises TRACK_NOT_FOUND for t_ghost
# Initial state has playback_states showing t_ghost as current track.
# ============================================================================
@AppleMusicAPI._register_patch("rate_track", "s68_ghost_track")
def rate_track_s68_ghost_track(self, track_id, rating):
    if track_id == "t_ghost":
        raise AppleMusicError(
            error_code="TRACK_NOT_FOUND",
            message=f"Track '{track_id}' not found in the catalog.",
            suggested_action="Use search_catalog() to find valid track IDs.",
            context={"track_id": track_id},
        )
    return self._original_function(track_id, rating)


# ============================================================================
# S71: Chrome Butterfly removed from AM catalog
# Trigger: search_catalog returns empty tracks for "Chrome Butterfly"
# Also: add_to_up_next will fail with TRACK_NOT_FOUND via normal code path
#        if the track isn't in catalog_tracks.
# ============================================================================
@AppleMusicAPI._register_patch("search_catalog", "s71_chrome_butterfly_removed")
def search_catalog_s71_chrome_butterfly_removed(self, query, types=None, limit=10):
    result = self._original_function(query, types, limit)
    if "chrome butterfly" in query.lower():
        if "tracks" in result:
            result["tracks"] = []
    return result


# ============================================================================
# S74: Stale recently_added — returns months-old IU album
# Trigger: get_recently_added returns hardcoded stale data
# ============================================================================
@AppleMusicAPI._register_patch("get_recently_added", "s74_stale_recently_added")
def get_recently_added_s74_stale_recently_added(self, limit=20):
    return [
        {
            "item_id": "alb_old_iu",
            "item_type": "album",
            "added_at": "2025-01-10T08:00:00Z",
        }
    ][:max(1, int(limit))]


# ============================================================================
# S76: King Solace removed from AM
# Trigger: search_catalog returns empty artists for "King Solace"
# ============================================================================
@AppleMusicAPI._register_patch("search_catalog", "s76_king_solace_removed")
def search_catalog_s76_king_solace_removed(self, query, types=None, limit=10):
    result = self._original_function(query, types, limit)
    if "king solace" in query.lower():
        if "artists" in result:
            result["artists"] = []
    return result


# ============================================================================
# S77: Stale playback — shows BTS Butter from 10 min ago
# Trigger: get_playback_state returns hardcoded stale data
# position_ms=180000 (3 min in) creates contradiction when user says
# "I just skipped a couple tracks"
# ============================================================================
@AppleMusicAPI._register_patch("get_playback_state", "s77_stale_playback")
def get_playback_state_s77_stale_playback(self):
    return {
        "track_id": "t_butter",
        "station_id": None,
        "position_ms": 180000,
        "is_playing": True,
        "shuffle": False,
        "repeat_mode": "off",
    }


# ============================================================================
# S79: No active playback — session expired
# Trigger: skip_to_next raises NO_ACTIVE_PLAYBACK
# ============================================================================
@AppleMusicAPI._register_patch("skip_to_next", "s79_no_active_playback")
def skip_to_next_s79_no_active_playback(self):
    raise AppleMusicError(
        error_code="NO_ACTIVE_PLAYBACK",
        message="No active playback session found.",
        suggested_action="Start playback first with play_track(), play_album(), or play_station().",
        context={"user_id": self.user_id},
    )
