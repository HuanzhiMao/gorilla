"""
Spotify Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Models Spotify-specific concepts: device-bound playback, collaborative playlists,
  context_uri, Spotify Connect transfer, podcasts, and seed-based recommendations.
"""

from __future__ import annotations

import copy
import math
import random
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from .base_service import BaseServiceAPI


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class SpotifyError(Exception):
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


def _clamp(x: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, x))


# ---------------------------------------------------------------------------
# Spotify API
# ---------------------------------------------------------------------------


DEFAULT_STATE = {
    "random_seed": 42,
    "profile": {},
    "player": {},
    "playlists": {},
    "artists": {},
    "albums": {},
    "songs": {},
    "shows": {},
    "episodes": {},
    "followed_users": {},
}


class SpotifyAPI(BaseServiceAPI):
    """
    In-memory dummy implementation of a Spotify-like music streaming service.
    Supports device-bound playback, collaborative playlists, Spotify Connect,
    context URIs, podcasts, and seed-based recommendations.
    """

    _STATE_KEYS = (
        "profile", "player", "playlists",
        "artists", "albums", "songs",
        "shows", "episodes", "followed_users",
    )
    _ID_COUNTER_DEFAULTS = {
        "playlist": 0,
        "device": 0,
    }
    _DEFAULT_SEED = 42

    def __init__(self):
        super().__init__()
        self.profile: Dict[str, Any]
        self.player: Dict[str, Any]
        self.playlists: Dict[str, Dict[str, Any]]
        self.artists: Dict[str, Dict[str, Any]]
        self.albums: Dict[str, Dict[str, Any]]
        self.songs: Dict[str, Dict[str, Any]]
        self.shows: Dict[str, Dict[str, Any]]
        self.episodes: Dict[str, Dict[str, Any]]
        self.followed_users: Dict[str, List[str]]
        self._api_description = (
            "This tool belongs to the Spotify music streaming system, which allows "
            "users to search for music, manage playlists, control playback across "
            "devices, save tracks and albums, follow artists, and listen to podcasts."
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
        self._random = random.Random(
            scenario.get("random_seed", DEFAULT_STATE_COPY["random_seed"])
        )
        self.profile = scenario.get("profile", DEFAULT_STATE_COPY["profile"])
        self.player = scenario.get("player", DEFAULT_STATE_COPY["player"])
        self.playlists = scenario.get("playlists", DEFAULT_STATE_COPY["playlists"])
        self.artists = scenario.get("artists", DEFAULT_STATE_COPY["artists"])
        self.albums = scenario.get("albums", DEFAULT_STATE_COPY["albums"])
        self.songs = scenario.get("songs", DEFAULT_STATE_COPY["songs"])
        self.shows = scenario.get("shows", DEFAULT_STATE_COPY["shows"])
        self.episodes = scenario.get("episodes", DEFAULT_STATE_COPY["episodes"])
        self.followed_users = scenario.get("followed_users", DEFAULT_STATE_COPY["followed_users"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, SpotifyAPI):
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
    # Internal mechanics
    # -----------------------------------------------------------------------

    def _require_song(self, track_id: str) -> Dict[str, Any]:
        song = self.songs.get(track_id)
        if not song:
            raise SpotifyError(
                "TRACK_NOT_FOUND",
                f"Track '{track_id}' not found.",
                suggested_action="Use search_tracks() to find valid track IDs.",
                context={"track_id": track_id},
            )
        return song

    def _require_album(self, album_id: str) -> Dict[str, Any]:
        album = self.albums.get(album_id)
        if not album:
            raise SpotifyError(
                "ALBUM_NOT_FOUND",
                f"Album '{album_id}' not found.",
                suggested_action="Use search_albums() to find valid album IDs.",
                context={"album_id": album_id},
            )
        return album

    def _require_artist(self, artist_id: str) -> Dict[str, Any]:
        artist = self.artists.get(artist_id)
        if not artist:
            raise SpotifyError(
                "ARTIST_NOT_FOUND",
                f"Artist '{artist_id}' not found.",
                suggested_action="Use search_artists() to find valid artist IDs.",
                context={"artist_id": artist_id},
            )
        return artist

    def _require_playlist(self, playlist_id: str) -> Dict[str, Any]:
        playlist = self.playlists.get(playlist_id)
        if not playlist:
            raise SpotifyError(
                "PLAYLIST_NOT_FOUND",
                f"Playlist '{playlist_id}' not found.",
                suggested_action="Use get_user_playlists() to find valid playlist IDs.",
                context={"playlist_id": playlist_id},
            )
        return playlist

    def _require_device(self, device_id: str) -> Dict[str, Any]:
        for d in self.profile.get("devices", []):
            if d.get("device_id") == device_id:
                return d
        raise SpotifyError(
            "DEVICE_NOT_FOUND",
            f"Device '{device_id}' not found.",
            suggested_action="Use get_devices() to list available devices.",
            context={"device_id": device_id},
        )

    def _get_active_device(self) -> Optional[Dict[str, Any]]:
        """Return the currently active device, or None."""
        for d in self.profile.get("devices", []):
            if d.get("is_active"):
                return d
        return None

    def _ensure_playback(self) -> Dict[str, Any]:
        """Return existing playback state, or raise if none exists."""
        if not self.player or not self.player.get("current_song_id"):
            raise SpotifyError(
                "NO_ACTIVE_PLAYBACK",
                "No active playback session found.",
                suggested_action="Start playback with play_track() or play_context() first.",
                context={"user_id": self.user_id},
            )
        return self.player

    def _get_queue(self) -> List[str]:
        """Return or initialize the queue song IDs list."""
        return self.player.setdefault("queue_song_ids", [])

    # -----------------------------------------------------------------------
    # Search & Discovery
    # -----------------------------------------------------------------------

    def search_tracks(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search the catalog for tracks matching a text query.

        Args:
            query (str): Free-text search string matched against track name
                and artist name. Pass an empty string to return all tracks.
            limit (int): Maximum number of results to return. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Matching tracks, each with fields:
                song_id (str), name (str), artist_id (List[str]), album_id (str),
                duration_ms (int), explicit (bool), genre (List[str]),
                play_count (int), saved (bool).
        """
        results = []
        for t in self.songs.values():
            if _matches_query(t.get("name", ""), query):
                results.append(deepcopy(t))
                continue
            # Check against artist names (artist_id is now a list)
            artist_ids = t.get("artist_id", [])
            if isinstance(artist_ids, str):
                artist_ids = [artist_ids]
            matched = False
            for aid in artist_ids:
                artist = self.artists.get(aid)
                if artist and _matches_query(artist.get("name", ""), query):
                    results.append(deepcopy(t))
                    matched = True
                    break
            if matched:
                continue
        return results[: max(1, int(limit))]

    def search_albums(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search the catalog for albums matching a text query.

        Args:
            query (str): Free-text search string matched against album name
                and artist name.
            limit (int): Maximum number of results to return. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Matching albums, each with fields:
                album_id (str), name (str), artist_id (List[str]),
                songs (List[Dict]), release_date (str), genre (List[str]),
                saved (bool).
        """
        results = []
        for a in self.albums.values():
            if _matches_query(a.get("name", ""), query):
                results.append(deepcopy(a))
                continue
            # artist_id is now a list
            artist_ids = a.get("artist_id", [])
            if isinstance(artist_ids, str):
                artist_ids = [artist_ids]
            matched = False
            for aid in artist_ids:
                artist = self.artists.get(aid)
                if artist and _matches_query(artist.get("name", ""), query):
                    results.append(deepcopy(a))
                    matched = True
                    break
            if matched:
                continue
        return results[: max(1, int(limit))]

    def search_artists(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search the catalog for artists matching a text query.

        Args:
            query (str): Free-text search string matched against artist name.
            limit (int): Maximum number of results to return. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Matching artists, each with fields:
                artist_id (str), name (str), genre (List[str]),
                popularity (int), follower_count (int), following (bool),
                songs (List[Dict]).
        """
        results = []
        for a in self.artists.values():
            if _matches_query(a.get("name", ""), query):
                results.append(deepcopy(a))
        return results[: max(1, int(limit))]

    def get_track(self, track_id: str) -> Dict[str, Any]:
        """
        Get full details for a single track by ID.

        Args:
            track_id (str): The unique track identifier.

        Returns:
            Dict[str, Any]: Track object with fields:
                song_id (str), name (str), artist_id (List[str]), album_id (str),
                duration_ms (int), explicit (bool), genre (List[str]),
                play_count (int), saved (bool).
        """
        return deepcopy(self._require_song(track_id))

    def get_album(self, album_id: str) -> Dict[str, Any]:
        """
        Get full details for a single album by ID, including its track listing.

        Args:
            album_id (str): The unique album identifier.

        Returns:
            Dict[str, Any]: Album object with fields:
                album_id (str), name (str), artist_id (List[str]),
                songs (List[Dict]), release_date (str), genre (List[str]),
                saved (bool).
        """
        return deepcopy(self._require_album(album_id))

    def get_artist(self, artist_id: str) -> Dict[str, Any]:
        """
        Get full details for a single artist by ID.

        Args:
            artist_id (str): The unique artist identifier.

        Returns:
            Dict[str, Any]: Artist object with fields:
                artist_id (str), name (str), genre (List[str]),
                popularity (int), follower_count (int), following (bool),
                songs (List[Dict]).
        """
        return deepcopy(self._require_artist(artist_id))

    def get_artist_top_tracks(
        self,
        artist_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get the top tracks for an artist, sorted by popularity (simulated).

        Args:
            artist_id (str): The artist whose top tracks to retrieve.
            limit (int): Maximum number of tracks to return. Defaults to 5.

        Returns:
            List[Dict[str, Any]]: List of track objects for this artist,
                ordered by simulated popularity.
        """
        self._require_artist(artist_id)
        artist_tracks = [
            deepcopy(t)
            for t in self.songs.values()
            if artist_id in (t.get("artist_id") if isinstance(t.get("artist_id"), list) else [t.get("artist_id", "")])
        ]
        artist_tracks.sort(key=lambda t: t.get("duration_ms", 0), reverse=True)
        return artist_tracks[: max(1, int(limit))]

    def get_recommendations(
        self,
        seed_tracks: Optional[List[str]] = None,
        seed_artists: Optional[List[str]] = None,
        seed_genres: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get track recommendations based on seed tracks, artists, and/or genres.
        At least one seed must be provided. A maximum of 5 seeds total across
        all three seed types is allowed.

        Args:
            seed_tracks (List[str], optional): Track IDs to seed recommendations.
            seed_artists (List[str], optional): Artist IDs to seed recommendations.
            seed_genres (List[str], optional): Genre strings to seed recommendations.
            limit (int): Maximum number of recommendations. Defaults to 10.

        Returns:
            List[Dict[str, Any]]: Recommended track objects.
        """
        seeds_t = seed_tracks or []
        seeds_a = seed_artists or []
        seeds_g = seed_genres or []
        total_seeds = len(seeds_t) + len(seeds_a) + len(seeds_g)
        if total_seeds == 0:
            raise SpotifyError(
                "NO_SEEDS",
                "At least one seed (track, artist, or genre) is required.",
                suggested_action="Provide seed_tracks, seed_artists, or seed_genres.",
            )
        if total_seeds > 5:
            raise SpotifyError(
                "TOO_MANY_SEEDS",
                "A maximum of 5 seeds total is allowed.",
                suggested_action="Reduce the total number of seeds to 5 or fewer.",
                context={"total_seeds": total_seeds},
            )

        target_genres = set(seeds_g)
        target_artist_ids = set(seeds_a)
        for tid in seeds_t:
            t = self.songs.get(tid)
            if t:
                target_genres.update(t.get("genre", []))
                artist_ids = t.get("artist_id", [])
                if isinstance(artist_ids, str):
                    artist_ids = [artist_ids]
                target_artist_ids.update(artist_ids)
        for aid in target_artist_ids.copy():
            a = self.artists.get(aid)
            if a:
                target_genres.update(a.get("genre", []))

        seed_track_set = set(seeds_t)
        candidates = []
        for t in self.songs.values():
            if t.get("song_id") in seed_track_set:
                continue
            track_genres = set(t.get("genre", []))
            track_artist_ids = t.get("artist_id", [])
            if isinstance(track_artist_ids, str):
                track_artist_ids = [track_artist_ids]
            if track_genres & target_genres or set(track_artist_ids) & target_artist_ids:
                candidates.append(deepcopy(t))

        self._rng.shuffle(candidates)
        return candidates[: max(1, int(limit))]

    # -----------------------------------------------------------------------
    # Playlist management
    # -----------------------------------------------------------------------

    def get_user_playlists(self) -> List[Dict[str, Any]]:
        """
        Get all playlists owned by or visible to the current user, including
        collaborative playlists and the special 'Liked Songs' auto-playlist.

        Returns:
            List[Dict[str, Any]]: Playlist summaries, each with fields:
                playlist_id (str), name (str), owner_id (str),
                track_count (int), collaborative (bool), public (bool).
        """
        results = []
        for p in self.playlists.values():
            if (
                p.get("owner_id") == self.user_id
                or p.get("public", False)
                or p.get("collaborative", False)
            ):
                results.append(
                    {
                        "playlist_id": p["playlist_id"],
                        "name": p.get("name"),
                        "owner_id": p.get("owner_id"),
                        "track_count": len(p.get("songs", [])),
                        "collaborative": p.get("collaborative", False),
                        "public": p.get("public", False),
                    }
                )
        return results

    def get_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """
        Get full details for a playlist, including all track IDs.

        Args:
            playlist_id (str): The unique playlist identifier.

        Returns:
            Dict[str, Any]: Playlist object with fields:
                playlist_id (str), name (str), owner_id (str),
                songs (List[Dict]), collaborative (bool), public (bool),
                description (str).
        """
        return deepcopy(self._require_playlist(playlist_id))

    def create_playlist(
        self,
        name: str,
        description: str = "",
        public: bool = True,
        collaborative: bool = False,
    ) -> str:
        """
        Create a new playlist for the current user. Collaborative playlists
        cannot be public (Spotify enforces this constraint).

        Args:
            name (str): Display name for the playlist.
            description (str): Optional playlist description. Defaults to "".
            public (bool): Whether the playlist is publicly visible. Defaults to True.
            collaborative (bool): Whether other users can add tracks. Defaults to False.
                When True, the playlist is automatically set to non-public.

        Returns:
            str: The new playlist_id.
        """
        if not name or not name.strip():
            raise SpotifyError(
                "INVALID_PLAYLIST_NAME",
                "Playlist name cannot be empty.",
                suggested_action="Provide a non-empty playlist name.",
            )
        if collaborative:
            public = False

        playlist_id = self._new_id("playlist")
        self.playlists[playlist_id] = {
            "playlist_id": playlist_id,
            "name": name.strip(),
            "owner_id": self.user_id,
            "songs": [],
            "collaborative": collaborative,
            "public": public,
            "description": description,
            "created_at": _utc_now_iso(),
        }
        return playlist_id

    def add_tracks_to_playlist(
        self,
        playlist_id: str,
        track_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Add one or more tracks to a playlist. The current user must be the
        owner or the playlist must be collaborative.

        Args:
            playlist_id (str): The target playlist.
            track_ids (List[str]): List of track IDs to add.

        Returns:
            Dict[str, Any]: Updated playlist snapshot with fields:
                playlist_id (str), name (str), track_count (int),
                added (List[str]) listing the track IDs that were added.
        """
        playlist = self._require_playlist(playlist_id)
        if playlist.get("owner_id") != self.user_id and not playlist.get(
            "collaborative", False
        ):
            raise PermissionError("You do not have permission to access this resource.")
        if not track_ids:
            raise SpotifyError(
                "NO_TRACKS_PROVIDED",
                "At least one track_id must be provided.",
                suggested_action="Pass a non-empty list of track_ids.",
            )
        added = []
        for tid in track_ids:
            song = self._require_song(tid)
            # Append embedded song object to playlist
            embedded = {
                "song_id": song.get("song_id", tid),
                "name": song.get("name", ""),
                "genre": song.get("genre", []),
                "play_count": song.get("play_count", 0),
            }
            playlist["songs"].append(embedded)
            added.append(tid)
        return {
            "playlist_id": playlist_id,
            "name": playlist.get("name"),
            "track_count": len(playlist["songs"]),
            "added": added,
        }

    def remove_tracks_from_playlist(
        self,
        playlist_id: str,
        track_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Remove one or more tracks from a playlist. Removes only the first
        occurrence of each track_id.

        Args:
            playlist_id (str): The target playlist.
            track_ids (List[str]): List of track IDs to remove.

        Returns:
            Dict[str, Any]: Updated playlist snapshot with fields:
                playlist_id (str), name (str), track_count (int),
                removed (List[str]) listing track IDs that were actually removed.
        """
        playlist = self._require_playlist(playlist_id)
        if playlist.get("owner_id") != self.user_id and not playlist.get(
            "collaborative", False
        ):
            raise PermissionError("You do not have permission to access this resource.")
        removed = []
        for tid in track_ids:
            # Find and remove first embedded song object matching song_id
            for i, s in enumerate(playlist["songs"]):
                if s.get("song_id") == tid:
                    playlist["songs"].pop(i)
                    removed.append(tid)
                    break
        return {
            "playlist_id": playlist_id,
            "name": playlist.get("name"),
            "track_count": len(playlist["songs"]),
            "removed": removed,
        }

    def update_playlist_details(
        self,
        playlist_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        public: Optional[bool] = None,
        collaborative: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update metadata for a playlist. Only the owner can update playlist details.

        Args:
            playlist_id (str): The target playlist.
            name (str, optional): New display name.
            description (str, optional): New description.
            public (bool, optional): New public visibility setting.
            collaborative (bool, optional): New collaborative setting.

        Returns:
            Dict[str, Any]: Updated playlist object.
        """
        playlist = self._require_playlist(playlist_id)
        if playlist.get("owner_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        if name is not None:
            if not name.strip():
                raise SpotifyError(
                    "INVALID_PLAYLIST_NAME",
                    "Playlist name cannot be empty.",
                    suggested_action="Provide a non-empty name.",
                )
            playlist["name"] = name.strip()
        if description is not None:
            playlist["description"] = description
        if collaborative is not None:
            playlist["collaborative"] = collaborative
            if collaborative:
                playlist["public"] = False
        if public is not None and not playlist.get("collaborative", False):
            playlist["public"] = public
        return deepcopy(playlist)

    def delete_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """
        Delete (unfollow) a playlist. Only the owner can permanently delete it.

        Args:
            playlist_id (str): The playlist to delete.

        Returns:
            Dict[str, Any]: Confirmation with fields:
                deleted (bool), playlist_id (str).
        """
        playlist = self._require_playlist(playlist_id)
        if playlist.get("owner_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        del self.playlists[playlist_id]
        return {"deleted": True, "playlist_id": playlist_id}

    # -----------------------------------------------------------------------
    # Device & Spotify Connect
    # -----------------------------------------------------------------------

    def get_devices(self) -> List[Dict[str, Any]]:
        """
        Get all devices registered to the current user's Spotify account.

        Returns:
            List[Dict[str, Any]]: Device objects, each with fields:
                device_id (str), name (str),
                type (str e.g. "computer", "speaker"),
                is_active (bool), volume_percent (int 0-100).
        """
        return deepcopy(self.profile.get("devices", []))

    def transfer_playback(
        self,
        device_id: str,
        ensure_playback: bool = False,
    ) -> Dict[str, Any]:
        """
        Transfer playback to a different device (Spotify Connect). If
        ensure_playback is True and playback is paused, it will resume on the
        target device.

        Args:
            device_id (str): The target device to transfer to.
            ensure_playback (bool): If True, ensure music starts playing on the
                target device even if currently paused. Defaults to False.

        Returns:
            Dict[str, Any]: Transfer result with fields:
                transferred (bool), device_id (str), device_name (str),
                is_playing (bool).
        """
        device = self._require_device(device_id)

        # Deactivate all devices, then activate the target
        for d in self.profile.get("devices", []):
            d["is_active"] = False
        device["is_active"] = True

        # Update player state
        if self.player and self.player.get("current_song_id"):
            self.player["active_device_id"] = device_id
            if ensure_playback:
                self.player["is_playing"] = True
        elif ensure_playback:
            self.player.update({
                "active_device_id": device_id,
                "current_song_id": None,
                "context_uri": None,
                "position_ms": 0,
                "is_playing": False,
                "shuffle": False,
                "repeat_mode": "off",
            })

        is_playing = self.player.get("is_playing", False) if self.player else False
        return {
            "transferred": True,
            "device_id": device_id,
            "device_name": device.get("name"),
            "is_playing": is_playing,
        }

    def set_volume(self, volume_percent: int) -> Dict[str, Any]:
        """
        Set the volume on the current user's active device.

        Args:
            volume_percent (int): Volume level from 0 to 100.

        Returns:
            Dict[str, Any]: Result with fields:
                device_id (str), volume_percent (int).
        """
        device = self._get_active_device()
        if not device:
            raise SpotifyError(
                "NO_ACTIVE_DEVICE",
                "No active device found for this user.",
                suggested_action="Transfer playback to a device first with transfer_playback().",
                context={"user_id": self.user_id},
            )
        vol = _clamp(int(volume_percent), 0, 100)
        device["volume_percent"] = vol
        return {"device_id": device["device_id"], "volume_percent": vol}

    # -----------------------------------------------------------------------
    # Playback control
    # -----------------------------------------------------------------------

    def play_track(
        self,
        track_id: str,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start playing a specific track. If no device_id is provided, playback
        begins on the current user's currently active device.

        Args:
            track_id (str): The track to play.
            device_id (str, optional): Target device. Defaults to the active device.

        Returns:
            Dict[str, Any]: Playback state with fields:
                current_song_id (str), active_device_id (str), is_playing (bool),
                position_ms (int), context_uri (str | None).
        """
        self._require_song(track_id)

        if device_id:
            device = self._require_device(device_id)
            for d in self.profile.get("devices", []):
                d["is_active"] = False
            device["is_active"] = True
        else:
            device = self._get_active_device()
            if not device:
                raise SpotifyError(
                    "NO_ACTIVE_DEVICE",
                    "No active device found. Specify a device_id or transfer playback first.",
                    suggested_action="Call get_devices() and transfer_playback().",
                    context={"user_id": self.user_id},
                )

        self.player.update({
            "active_device_id": device["device_id"],
            "current_song_id": track_id,
            "context_uri": None,
            "position_ms": 0,
            "is_playing": True,
            "shuffle": self.player.get("shuffle", False),
            "repeat_mode": self.player.get("repeat_mode", "off"),
        })

        # Update queue: set current track, keep existing queue
        self.player["queue_song_ids"] = self._get_queue()

        return deepcopy(self.player)

    def play_context(
        self,
        context_uri: str,
        offset: int = 0,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start playing within a context (album or playlist). The context_uri
        should be in the format "album:<album_id>" or "playlist:<playlist_id>".
        Playback starts at the given offset index within the context.

        Args:
            context_uri (str): Context to play, e.g. "album:alb_1" or "playlist:pl_1".
            offset (int): Zero-based index of the track to start from within the
                context. Defaults to 0.
            device_id (str, optional): Target device. Defaults to the active device.

        Returns:
            Dict[str, Any]: Playback state with fields:
                current_song_id (str), active_device_id (str), is_playing (bool),
                position_ms (int), context_uri (str).
        """
        parts = context_uri.split(":", 1)
        if len(parts) != 2 or parts[0] not in ("album", "playlist"):
            raise SpotifyError(
                "INVALID_CONTEXT_URI",
                "context_uri must be in format 'album:<id>' or 'playlist:<id>'.",
                suggested_action="Use format 'album:<album_id>' or 'playlist:<playlist_id>'.",
                context={"context_uri": context_uri},
            )

        ctx_type, ctx_id = parts
        if ctx_type == "album":
            album = self._require_album(ctx_id)
            # Extract song IDs from embedded song objects
            track_list = [s["song_id"] for s in album.get("songs", [])]
        else:
            playlist = self._require_playlist(ctx_id)
            # Extract song IDs from embedded song objects
            track_list = [s["song_id"] for s in playlist.get("songs", [])]

        if not track_list:
            raise SpotifyError(
                "EMPTY_CONTEXT",
                "The context contains no tracks.",
                suggested_action="Choose a context with at least one track.",
                context={"context_uri": context_uri},
            )

        idx = _clamp(int(offset), 0, len(track_list) - 1)
        track_id = track_list[idx]

        if device_id:
            device = self._require_device(device_id)
            for d in self.profile.get("devices", []):
                d["is_active"] = False
            device["is_active"] = True
        else:
            device = self._get_active_device()
            if not device:
                raise SpotifyError(
                    "NO_ACTIVE_DEVICE",
                    "No active device found. Specify a device_id or transfer playback first.",
                    suggested_action="Call get_devices() and transfer_playback().",
                    context={"user_id": self.user_id},
                )

        self.player.update({
            "active_device_id": device["device_id"],
            "current_song_id": track_id,
            "context_uri": context_uri,
            "position_ms": 0,
            "is_playing": True,
            "shuffle": self.player.get("shuffle", False),
            "repeat_mode": self.player.get("repeat_mode", "off"),
        })

        # Set queue to remaining tracks in context
        remaining = track_list[idx + 1:]
        self.player["queue_song_ids"] = list(remaining)

        return deepcopy(self.player)

    def pause_playback(self) -> Dict[str, Any]:
        """
        Pause playback on the current user's active device.

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        pb = self._ensure_playback()
        pb["is_playing"] = False
        return deepcopy(pb)

    def resume_playback(self) -> Dict[str, Any]:
        """
        Resume playback on the current user's active device.

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        pb = self._ensure_playback()
        if not pb.get("current_song_id"):
            raise SpotifyError(
                "NOTHING_TO_RESUME",
                "No track is loaded to resume.",
                suggested_action="Play a track first with play_track() or play_context().",
                context={"user_id": self.user_id},
            )
        pb["is_playing"] = True
        return deepcopy(pb)

    def skip_to_next(self) -> Dict[str, Any]:
        """
        Skip to the next track in the queue or context. If the queue is empty
        and no context is set, playback stops.

        Returns:
            Dict[str, Any]: Updated playback state. The current_song_id field reflects
                the new current track, or None if nothing is left to play.
        """
        pb = self._ensure_playback()
        queue = self._get_queue()

        if queue:
            next_track = queue.pop(0)
            pb["current_song_id"] = next_track
            pb["position_ms"] = 0
        else:
            pb["current_song_id"] = None
            pb["is_playing"] = False
            pb["position_ms"] = 0

        return deepcopy(pb)

    def skip_to_previous(self) -> Dict[str, Any]:
        """
        Skip to the previous track. In this simplified model, if the current
        position is more than 3 seconds in, it restarts the current track.
        Otherwise it signals no previous track is available.

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        pb = self._ensure_playback()
        if pb.get("position_ms", 0) > 3000:
            pb["position_ms"] = 0
        return deepcopy(pb)

    def seek_track(self, position_ms: int) -> Dict[str, Any]:
        """
        Seek to a position in the currently playing track.

        Args:
            position_ms (int): Target position in milliseconds. Must be >= 0.

        Returns:
            Dict[str, Any]: Updated playback state reflecting the new position.
        """
        pb = self._ensure_playback()
        pos = max(0, int(position_ms))
        song = self.songs.get(pb.get("current_song_id", ""))
        if song:
            pos = min(pos, song.get("duration_ms", pos))
        pb["position_ms"] = pos
        return deepcopy(pb)

    def set_shuffle(self, state: bool) -> Dict[str, Any]:
        """
        Toggle shuffle mode on the current user's playback.

        Args:
            state (bool): True to enable shuffle, False to disable.

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        pb = self._ensure_playback()
        pb["shuffle"] = bool(state)
        return deepcopy(pb)

    def set_repeat(self, mode: str) -> Dict[str, Any]:
        """
        Set the repeat mode on the current user's playback.

        Args:
            mode (str): One of "off", "track", or "context".

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        if mode not in ("off", "track", "context"):
            raise SpotifyError(
                "INVALID_REPEAT_MODE",
                f"Invalid repeat mode '{mode}'. Must be 'off', 'track', or 'context'.",
                suggested_action="Use one of: 'off', 'track', 'context'.",
                context={"mode": mode},
            )
        pb = self._ensure_playback()
        pb["repeat_mode"] = mode
        return deepcopy(pb)

    def get_playback_state(self) -> Dict[str, Any]:
        """
        Get the current playback state for the current user, including the
        active device and current track information.

        Returns:
            Dict[str, Any]: Playback state with fields:
                active_device_id (str), current_song_id (str | None),
                context_uri (str | None), position_ms (int), is_playing (bool),
                shuffle (bool), repeat_mode (str), device (Dict | None with device details).
        """
        if not self.player or not self.player.get("current_song_id"):
            return {
                "active_device_id": None,
                "current_song_id": None,
                "context_uri": None,
                "position_ms": 0,
                "is_playing": False,
                "shuffle": False,
                "repeat_mode": "off",
                "device": None,
            }
        result = deepcopy(self.player)
        # Find device from profile devices list
        device = None
        active_device_id = self.player.get("active_device_id", "")
        for d in self.profile.get("devices", []):
            if d.get("device_id") == active_device_id:
                device = d
                break
        result["device"] = deepcopy(device) if device else None
        return result

    # -----------------------------------------------------------------------
    # Queue management
    # -----------------------------------------------------------------------

    def add_to_queue(self, track_id: str) -> Dict[str, Any]:
        """
        Add a track to the end of the current user's playback queue.

        Args:
            track_id (str): The track to enqueue.

        Returns:
            Dict[str, Any]: Queue snapshot with fields:
                current_song_id (str | None), queue_length (int),
                added_track (str).
        """
        self._require_song(track_id)
        queue = self._get_queue()
        queue.append(track_id)
        return {
            "current_song_id": self.player.get("current_song_id"),
            "queue_length": len(queue),
            "added_track": track_id,
        }

    def get_queue(self) -> Dict[str, Any]:
        """
        Get the current user's playback queue.

        Returns:
            Dict[str, Any]: Queue object with fields:
                current_song_id (str | None), queue (List[str]).
        """
        queue = self._get_queue()
        return {
            "current_song_id": self.player.get("current_song_id"),
            "queue": list(queue),
        }

    def clear_queue(self) -> Dict[str, Any]:
        """
        Clear all upcoming tracks from the current user's queue. The currently
        playing track is not affected.

        Returns:
            Dict[str, Any]: Confirmation with fields:
                cleared (bool), current_song_id (str | None).
        """
        self.player["queue_song_ids"] = []
        return {"cleared": True, "current_song_id": self.player.get("current_song_id")}

    # -----------------------------------------------------------------------
    # User library (Liked Songs, saved albums, followed artists)
    # -----------------------------------------------------------------------

    def save_tracks(self, track_ids: List[str]) -> Dict[str, Any]:
        """
        Save tracks to the current user's 'Liked Songs' library.

        Args:
            track_ids (List[str]): Track IDs to save.

        Returns:
            Dict[str, Any]: Result with fields:
                saved (List[str]), total_saved (int).
        """
        saved = []
        for tid in track_ids:
            song = self._require_song(tid)
            if not song.get("saved", False):
                song["saved"] = True
                saved.append(tid)
        total_saved = sum(1 for s in self.songs.values() if s.get("saved"))
        return {"saved": saved, "total_saved": total_saved}

    def unsave_tracks(self, track_ids: List[str]) -> Dict[str, Any]:
        """
        Remove tracks from the current user's 'Liked Songs' library.

        Args:
            track_ids (List[str]): Track IDs to remove.

        Returns:
            Dict[str, Any]: Result with fields:
                removed (List[str]), total_saved (int).
        """
        removed = []
        for tid in track_ids:
            song = self.songs.get(tid)
            if song and song.get("saved", False):
                song["saved"] = False
                removed.append(tid)
        total_saved = sum(1 for s in self.songs.values() if s.get("saved"))
        return {"removed": removed, "total_saved": total_saved}

    def get_saved_tracks(self) -> List[str]:
        """
        Get the current user's 'Liked Songs' (saved tracks).

        Returns:
            List[str]: List of saved track IDs.
        """
        return [sid for sid, s in self.songs.items() if s.get("saved")]

    def save_albums(self, album_ids: List[str]) -> Dict[str, Any]:
        """
        Save albums to the current user's library.

        Args:
            album_ids (List[str]): Album IDs to save.

        Returns:
            Dict[str, Any]: Result with fields:
                saved (List[str]), total_saved (int).
        """
        saved = []
        for aid in album_ids:
            album = self._require_album(aid)
            if not album.get("saved", False):
                album["saved"] = True
                saved.append(aid)
        total_saved = sum(1 for a in self.albums.values() if a.get("saved"))
        return {"saved": saved, "total_saved": total_saved}

    def unsave_albums(self, album_ids: List[str]) -> Dict[str, Any]:
        """
        Remove albums from the current user's library.

        Args:
            album_ids (List[str]): Album IDs to remove.

        Returns:
            Dict[str, Any]: Result with fields:
                removed (List[str]), total_saved (int).
        """
        removed = []
        for aid in album_ids:
            album = self.albums.get(aid)
            if album and album.get("saved", False):
                album["saved"] = False
                removed.append(aid)
        total_saved = sum(1 for a in self.albums.values() if a.get("saved"))
        return {"removed": removed, "total_saved": total_saved}

    def get_saved_albums(self) -> List[str]:
        """
        Get the current user's saved albums.

        Returns:
            List[str]: List of saved album IDs.
        """
        return [aid for aid, a in self.albums.items() if a.get("saved")]

    # -----------------------------------------------------------------------
    # Social / following
    # -----------------------------------------------------------------------

    def follow_artist(self, artist_id: str) -> Dict[str, Any]:
        """
        Follow an artist.

        Args:
            artist_id (str): The artist to follow.

        Returns:
            Dict[str, Any]: Result with fields:
                followed (bool), artist_id (str), total_followed (int).
        """
        artist = self._require_artist(artist_id)
        followed_list = [aid for aid, a in self.artists.items() if a.get("following")]
        if artist.get("following"):
            return {
                "followed": False,
                "artist_id": artist_id,
                "total_followed": len(followed_list),
                "message": "Already following this artist.",
            }
        artist["following"] = True
        followed_list = [aid for aid, a in self.artists.items() if a.get("following")]
        return {
            "followed": True,
            "artist_id": artist_id,
            "total_followed": len(followed_list),
        }

    def unfollow_artist(self, artist_id: str) -> Dict[str, Any]:
        """
        Unfollow an artist.

        Args:
            artist_id (str): The artist to unfollow.

        Returns:
            Dict[str, Any]: Result with fields:
                unfollowed (bool), artist_id (str), total_followed (int).
        """
        artist = self.artists.get(artist_id)
        followed_list = [aid for aid, a in self.artists.items() if a.get("following")]
        if not artist or not artist.get("following"):
            return {
                "unfollowed": False,
                "artist_id": artist_id,
                "total_followed": len(followed_list),
                "message": "Not currently following this artist.",
            }
        artist["following"] = False
        followed_list = [aid for aid, a in self.artists.items() if a.get("following")]
        return {
            "unfollowed": True,
            "artist_id": artist_id,
            "total_followed": len(followed_list),
        }

    def get_followed_artists(self) -> List[Dict[str, Any]]:
        """
        Get the list of artists the current user is following.

        Returns:
            List[Dict[str, Any]]: List of artist objects for followed artists.
        """
        results = []
        for aid, a in self.artists.items():
            if a.get("following"):
                results.append(deepcopy(a))
        return results

    def follow_user(self, target_user_id: str) -> Dict[str, Any]:
        """
        Follow another user on Spotify.

        Args:
            target_user_id (str): The user to follow.

        Returns:
            Dict[str, Any]: Result with fields:
                followed (bool), target_user_id (str).
        """
        if self.user_id == target_user_id:
            raise SpotifyError(
                "CANNOT_FOLLOW_SELF",
                "A user cannot follow themselves.",
                suggested_action="Provide a different target_user_id.",
                context={"user_id": self.user_id},
            )
        if self.user_id not in self.followed_users:
            self.followed_users[self.user_id] = []
        if target_user_id in self.followed_users[self.user_id]:
            return {
                "followed": False,
                "target_user_id": target_user_id,
                "message": "Already following this user.",
            }
        self.followed_users[self.user_id].append(target_user_id)
        return {"followed": True, "target_user_id": target_user_id}

    def unfollow_user(self, target_user_id: str) -> Dict[str, Any]:
        """
        Unfollow another user on Spotify.

        Args:
            target_user_id (str): The user to unfollow.

        Returns:
            Dict[str, Any]: Result with fields:
                unfollowed (bool), target_user_id (str).
        """
        if self.user_id not in self.followed_users:
            self.followed_users[self.user_id] = []
        if target_user_id not in self.followed_users[self.user_id]:
            return {
                "unfollowed": False,
                "target_user_id": target_user_id,
                "message": "Not currently following this user.",
            }
        self.followed_users[self.user_id].remove(target_user_id)
        return {"unfollowed": True, "target_user_id": target_user_id}

    def share_track(self, track_id: str) -> Dict[str, Any]:
        """
        Generate a shareable link for a track.

        Args:
            track_id (str): The track to share.

        Returns:
            Dict[str, Any]: Result with fields:
                share_url (str), track_id (str), shared_by (str).
        """
        self._require_song(track_id)
        return {
            "share_url": f"https://open.spotify.com/track/{track_id}",
            "track_id": track_id,
            "shared_by": self.user_id,
        }

    # -----------------------------------------------------------------------
    # Podcasts (shows & episodes)
    # -----------------------------------------------------------------------

    def get_show(self, show_id: str) -> Dict[str, Any]:
        """
        Get details for a podcast show.

        Args:
            show_id (str): The unique show identifier.

        Returns:
            Dict[str, Any]: Show object with fields:
                show_id (str), name (str), publisher (str),
                description (str), episodes (List[str]).
        """
        show = self.shows.get(show_id)
        if not show:
            raise SpotifyError(
                "SHOW_NOT_FOUND",
                f"Show '{show_id}' not found.",
                suggested_action="Search for shows or verify the show_id.",
                context={"show_id": show_id},
            )
        return deepcopy(show)

    def get_episode(self, episode_id: str) -> Dict[str, Any]:
        """
        Get details for a podcast episode.

        Args:
            episode_id (str): The unique episode identifier.

        Returns:
            Dict[str, Any]: Episode object with fields:
                episode_id (str), show_id (str), name (str),
                duration_ms (int), description (str), release_date (str).
        """
        ep = self.episodes.get(episode_id)
        if not ep:
            raise SpotifyError(
                "EPISODE_NOT_FOUND",
                f"Episode '{episode_id}' not found.",
                suggested_action="Use get_show() to list episodes for a show.",
                context={"episode_id": episode_id},
            )
        return deepcopy(ep)

    def play_episode(
        self,
        episode_id: str,
        device_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start playing a podcast episode. If no device_id is provided,
        playback begins on the current user's currently active device.

        Args:
            episode_id (str): The episode to play.
            device_id (str, optional): Target device. Defaults to active device.

        Returns:
            Dict[str, Any]: Playback state with fields:
                current_song_id (str, set to the episode_id for podcasts),
                active_device_id (str), is_playing (bool), position_ms (int),
                context_uri (str, format "show:<show_id>").
        """
        ep = self.episodes.get(episode_id)
        if not ep:
            raise SpotifyError(
                "EPISODE_NOT_FOUND",
                f"Episode '{episode_id}' not found.",
                suggested_action="Use get_show() to find valid episode IDs.",
                context={"episode_id": episode_id},
            )

        if device_id:
            device = self._require_device(device_id)
            for d in self.profile.get("devices", []):
                d["is_active"] = False
            device["is_active"] = True
        else:
            device = self._get_active_device()
            if not device:
                raise SpotifyError(
                    "NO_ACTIVE_DEVICE",
                    "No active device found.",
                    suggested_action="Call get_devices() and transfer_playback().",
                    context={"user_id": self.user_id},
                )

        show_id = ep.get("show_id", "")
        self.player.update({
            "active_device_id": device["device_id"],
            "current_song_id": episode_id,
            "context_uri": f"show:{show_id}",
            "position_ms": 0,
            "is_playing": True,
            "shuffle": False,
            "repeat_mode": "off",
        })
        return deepcopy(self.player)

    # -----------------------------------------------------------------------
    # Account info
    # -----------------------------------------------------------------------

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get profile information for the current user.

        Returns:
            Dict[str, Any]: User profile with fields:
                user_id (str), name (str), email (str), premium (bool),
                country (str), following (int).
        """
        following_count = len(self.followed_users.get(self.user_id, []))
        return {
            "user_id": self.user_id,
            "name": self.profile.get("name"),
            "email": self.profile.get("email"),
            "premium": self.profile.get("premium", False),
            "country": self.profile.get("country", ""),
            "following": following_count,
        }

    def get_public_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Get limited public profile information for another user.

        Args:
            user_id (str): The user whose public profile to retrieve.

        Returns:
            Dict[str, Any]: Public profile with fields:
                display_name (str), username (str).
        """
        # In the new single-user model, we can only return our own profile info
        if user_id == self.user_id:
            return {
                "display_name": self.profile.get("name", ""),
                "username": user_id,
            }
        # For other users, return minimal info
        return {
            "display_name": user_id,
            "username": user_id,
        }
