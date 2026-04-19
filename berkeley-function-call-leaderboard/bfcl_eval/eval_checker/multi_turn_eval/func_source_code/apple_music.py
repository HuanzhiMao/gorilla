"""
Apple Music Dummy API (in-memory, deterministic, benchmark-friendly)

Design goals:
- No real network requests; pure function calls.
- Explicit in-memory state seeded via _load_scenario().
- Structured errors (error_code, message, suggested_action, context).
- Models Apple Music-specific concepts: library-centric workflow, ratings
  (love/dislike), stations, Up Next queue, account-level playback (no device
  concept), smart playlists, editorial content, and recently played/added queries.
"""

from __future__ import annotations

import copy
import math
import random
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

from .server_patch_mixin import PatchableMixin


# ---------------------------------------------------------------------------
# Error model
# ---------------------------------------------------------------------------


class AppleMusicError(Exception):
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


DEFAULT_STATE = {
    "random_seed": 99,
    "profile": {},
    "player": {},
    "playlists": {},
    "artists": {},
    "albums": {},
    "songs": {},
    "stations": {},
    "ratings": {},
    "recently_played": {},
    "recently_added": {},
    "editorial_content": {},
    "sing_catalog": {},
    "replay": {},
    "audio_settings": {},
}


class AppleMusicAPI(PatchableMixin):
    """
    In-memory dummy implementation of an Apple Music-like streaming service.
    Supports library-centric workflow, love/dislike ratings, curated stations,
    Up Next queue, smart playlists, editorial content, and account-level
    playback without explicit device management.
    """


    def __init__(self):
        self._id_counters = {"playlist": 0, "station": 0}
        self.profile: Dict[str, Any]
        self.player: Dict[str, Any]
        self.playlists: Dict[str, Dict[str, Any]]
        self.artists: Dict[str, Dict[str, Any]]
        self.albums: Dict[str, Dict[str, Any]]
        self.songs: Dict[str, Dict[str, Any]]
        self.stations: Dict[str, Dict[str, Any]]
        self.ratings: Dict[str, str]
        self.recently_played: List[Dict[str, Any]]
        self.recently_added: List[Dict[str, Any]]
        self.editorial_content: Dict[str, Dict[str, Any]]
        self.sing_catalog: Dict[str, Dict[str, Any]]
        self.replay: Dict[str, Dict[str, Any]]
        self.audio_settings: Dict[str, Any]
        self._api_description = (
            "This tool belongs to the Apple Music streaming system, which allows "
            "users to search the catalog, manage their personal library, create "
            "playlists, control playback, rate tracks, listen to curated stations, "
            "and discover new music through editorial content."
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
        self._random = random.Random(
            scenario.get("random_seed", DEFAULT_STATE_COPY["random_seed"])
        )
        # self.user_id is referenced throughout public methods (playlist
        # ownership, share_track, error contexts). Scenario files don't always
        # include it explicitly, so fall back to a safe default.
        self.user_id = scenario.get("user_id", "user_1")
        self.profile = scenario.get("profile", DEFAULT_STATE_COPY["profile"])
        self.player = scenario.get("player", DEFAULT_STATE_COPY["player"])
        self.playlists = scenario.get("playlists", DEFAULT_STATE_COPY["playlists"])
        self.artists = scenario.get("artists", DEFAULT_STATE_COPY["artists"])
        self.albums = scenario.get("albums", DEFAULT_STATE_COPY["albums"])
        self.songs = scenario.get("songs", DEFAULT_STATE_COPY["songs"])
        self.stations = scenario.get("stations", DEFAULT_STATE_COPY["stations"])
        self.ratings = scenario.get("ratings", DEFAULT_STATE_COPY["ratings"])
        self.recently_played = scenario.get("recently_played", DEFAULT_STATE_COPY["recently_played"])
        self.recently_added = scenario.get("recently_added", DEFAULT_STATE_COPY["recently_added"])
        self.editorial_content = scenario.get("editorial_content", DEFAULT_STATE_COPY["editorial_content"])
        self.sing_catalog = scenario.get("sing_catalog", DEFAULT_STATE_COPY["sing_catalog"])
        self.replay = scenario.get("replay", DEFAULT_STATE_COPY["replay"])
        self.audio_settings = scenario.get("audio_settings", DEFAULT_STATE_COPY["audio_settings"])
        self.long_context = long_context

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, AppleMusicAPI):
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

    def _require_catalog_track(self, track_id: str) -> Dict[str, Any]:
        track = self.songs.get(track_id)
        if not track:
            raise AppleMusicError(
                "TRACK_NOT_FOUND",
                f"Track '{track_id}' not found in the catalog.",
                suggested_action="Use search_catalog() to find valid track IDs.",
                context={"track_id": track_id},
            )
        return track

    def _require_catalog_album(self, album_id: str) -> Dict[str, Any]:
        album = self.albums.get(album_id)
        if not album:
            raise AppleMusicError(
                "ALBUM_NOT_FOUND",
                f"Album '{album_id}' not found in the catalog.",
                suggested_action="Use search_catalog() to find valid album IDs.",
                context={"album_id": album_id},
            )
        return album

    def _require_artist(self, artist_id: str) -> Dict[str, Any]:
        artist = self.artists.get(artist_id)
        if not artist:
            raise AppleMusicError(
                "ARTIST_NOT_FOUND",
                f"Artist '{artist_id}' not found.",
                suggested_action="Use search_catalog() to find valid artist IDs.",
                context={"artist_id": artist_id},
            )
        return artist

    def _require_playlist(self, playlist_id: str) -> Dict[str, Any]:
        playlist = self.playlists.get(playlist_id)
        if not playlist:
            raise AppleMusicError(
                "PLAYLIST_NOT_FOUND",
                f"Playlist '{playlist_id}' not found.",
                suggested_action="Use get_library_playlists() to find valid playlist IDs.",
                context={"playlist_id": playlist_id},
            )
        return playlist

    def _require_station(self, station_id: str) -> Dict[str, Any]:
        station = self.stations.get(station_id)
        if not station:
            raise AppleMusicError(
                "STATION_NOT_FOUND",
                f"Station '{station_id}' not found.",
                suggested_action="Use get_stations() to list available stations.",
                context={"station_id": station_id},
            )
        return station

    def _ensure_queue(self) -> List[str]:
        """Return or initialize the Up Next queue (flat list of song IDs)."""
        return self.player.setdefault("queue_song_ids", [])

    def _record_recently_played(self, track_id: str) -> None:
        """Add a track to the recently played list (max 50 entries)."""
        entry = {"track_id": track_id, "played_at": _utc_now_iso()}
        self.recently_played.insert(0, entry)
        self.recently_played[:] = self.recently_played[:50]

    def _record_recently_added(self, item_id: str, item_type: str) -> None:
        """Add an item to the recently added list (max 50 entries)."""
        entry = {"item_id": item_id, "item_type": item_type, "added_at": _utc_now_iso()}
        self.recently_added.insert(0, entry)
        self.recently_added[:] = self.recently_added[:50]

    # -----------------------------------------------------------------------
    # Search & Discovery
    # -----------------------------------------------------------------------

    def search_catalog(
        self,
        query: str,
        types: Optional[List[str]] = None,
        limit: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search the Apple Music catalog for tracks, albums, and/or artists.

        Args:
            query (str): Free-text search string. Pass an empty string to return all.
            types (List[str], optional): Resource types to include in results.
                Accepted values: "tracks", "albums", "artists". Defaults to all three.
            limit (int): Maximum number of results per type. Defaults to 10.

        Returns:
            Dict[str, List[Dict[str, Any]]]: Results keyed by type:
                tracks (List): Matching catalog track objects.
                albums (List): Matching catalog album objects.
                artists (List): Matching artist objects.
        """
        search_types = set(types or ["tracks", "albums", "artists"])
        lim = max(1, int(limit))
        results: Dict[str, List[Dict[str, Any]]] = {}

        if "tracks" in search_types:
            matched = []
            for t in self.songs.values():
                if _matches_query(t.get("name", ""), query):
                    matched.append(deepcopy(t))
                    continue
                # artist_id is now an array
                for aid in (t.get("artist_id") or []):
                    artist = self.artists.get(aid)
                    if artist and _matches_query(artist.get("name", ""), query):
                        matched.append(deepcopy(t))
                        break
            results["tracks"] = matched[:lim]

        if "albums" in search_types:
            matched = []
            for a in self.albums.values():
                if _matches_query(a.get("name", ""), query):
                    matched.append(deepcopy(a))
                    continue
                # artist_id is now an array
                for aid in (a.get("artist_id") or []):
                    artist = self.artists.get(aid)
                    if artist and _matches_query(artist.get("name", ""), query):
                        matched.append(deepcopy(a))
                        break
            results["albums"] = matched[:lim]

        if "artists" in search_types:
            matched = []
            for a in self.artists.values():
                if _matches_query(a.get("name", ""), query):
                    matched.append(deepcopy(a))
            results["artists"] = matched[:lim]

        return results

    def get_catalog_track(self, track_id: str) -> Dict[str, Any]:
        """
        Get full details for a catalog track.

        Args:
            track_id (str): The unique track identifier.

        Returns:
            Dict[str, Any]: Track object with fields:
                song_id (str), name (str), artist_id (List[str]), album_id (str),
                duration_ms (int), genre (List[str]), content_rating (str),
                play_count (int), saved (bool).
        """
        return deepcopy(self._require_catalog_track(track_id))

    def get_catalog_album(self, album_id: str) -> Dict[str, Any]:
        """
        Get full details for a catalog album, including its track listing.

        Args:
            album_id (str): The unique album identifier.

        Returns:
            Dict[str, Any]: Album object with fields:
                album_id (str), name (str), artist_id (List[str]),
                songs (List[Dict]), release_date (str), genre (List[str]),
                saved (bool).
        """
        return deepcopy(self._require_catalog_album(album_id))

    def get_artist(self, artist_id: str) -> Dict[str, Any]:
        """
        Get full details for an artist.

        Args:
            artist_id (str): The unique artist identifier.

        Returns:
            Dict[str, Any]: Artist object with fields:
                artist_id (str), name (str), genre (List[str]), url (str),
                songs (List[Dict]), follower_count (int), following (bool).
        """
        return deepcopy(self._require_artist(artist_id))

    def get_artist_top_tracks(
        self,
        artist_id: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Get the top tracks for an artist from the catalog, ordered by
        simulated popularity.

        Args:
            artist_id (str): The artist whose top tracks to retrieve.
            limit (int): Maximum number of tracks to return. Defaults to 5.

        Returns:
            List[Dict[str, Any]]: List of catalog track objects for this artist.
        """
        self._require_artist(artist_id)
        artist_tracks = [
            deepcopy(t)
            for t in self.songs.values()
            if artist_id in (t.get("artist_id") or [])
        ]
        artist_tracks.sort(key=lambda t: t.get("duration_ms", 0), reverse=True)
        return artist_tracks[: max(1, int(limit))]

    def get_editorial_content(
        self,
        content_id: Optional[str] = None,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Get Apple Music editorial content (curated playlists, featured albums,
        etc.). If a content_id is provided, returns that specific item.
        Otherwise returns all editorial content.

        Args:
            content_id (str, optional): Specific editorial content ID. If None,
                returns all available editorial content.

        Returns:
            Union[Dict[str, Any], List[Dict[str, Any]]]:
                Single editorial item or list of all editorial items. Each has:
                content_id (str), title (str), description (str),
                type (str, e.g. "curated_playlist", "featured_album"),
                target_id (str, the playlist or album ID).
        """
        if content_id:
            item = self.editorial_content.get(content_id)
            if not item:
                raise AppleMusicError(
                    "EDITORIAL_NOT_FOUND",
                    f"Editorial content '{content_id}' not found.",
                    suggested_action="Call get_editorial_content() without arguments to list all.",
                    context={"content_id": content_id},
                )
            return deepcopy(item)
        return [deepcopy(v) for v in self.editorial_content.values()]

    # -----------------------------------------------------------------------
    # Library management (add to library vs. just save)
    # -----------------------------------------------------------------------

    def add_tracks_to_library(
        self,
        track_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Add catalog tracks to the current user's personal library. This is the
        primary way users organize music in Apple Music.

        Args:
            track_ids (List[str]): Catalog track IDs to add to the library.

        Returns:
            Dict[str, Any]: Result with fields:
                added (List[str]), already_in_library (List[str]),
                total_library_tracks (int).
        """
        added = []
        already = []
        for tid in track_ids:
            song = self._require_catalog_track(tid)
            if song.get("saved"):
                already.append(tid)
            else:
                song["saved"] = True
                added.append(tid)
                self._record_recently_added(tid, "track")
        total = sum(1 for s in self.songs.values() if s.get("saved"))
        return {
            "added": added,
            "already_in_library": already,
            "total_library_tracks": total,
        }

    def remove_tracks_from_library(
        self,
        track_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Remove tracks from the current user's personal library.

        Args:
            track_ids (List[str]): Track IDs to remove from the library.

        Returns:
            Dict[str, Any]: Result with fields:
                removed (List[str]), not_in_library (List[str]),
                total_library_tracks (int).
        """
        removed = []
        not_found = []
        for tid in track_ids:
            song = self.songs.get(tid)
            if song and song.get("saved"):
                song["saved"] = False
                removed.append(tid)
            else:
                not_found.append(tid)
        total = sum(1 for s in self.songs.values() if s.get("saved"))
        return {
            "removed": removed,
            "not_in_library": not_found,
            "total_library_tracks": total,
        }

    def get_library_tracks(self) -> List[Dict[str, Any]]:
        """
        Get all tracks in the current user's personal library with full
        catalog details.

        Returns:
            List[Dict[str, Any]]: List of catalog track objects that are in
                the user's library.
        """
        results = []
        for sid, song in self.songs.items():
            if song.get("saved"):
                results.append(deepcopy(song))
        return results

    def add_albums_to_library(
        self,
        album_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Add catalog albums to the current user's personal library. Adding an
        album also adds all its tracks to the library.

        Args:
            album_ids (List[str]): Catalog album IDs to add.

        Returns:
            Dict[str, Any]: Result with fields:
                added_albums (List[str]), already_in_library (List[str]),
                tracks_added (int), total_library_albums (int).
        """
        added = []
        already = []
        tracks_added_count = 0
        for aid in album_ids:
            album = self._require_catalog_album(aid)
            if album.get("saved"):
                already.append(aid)
            else:
                album["saved"] = True
                added.append(aid)
                self._record_recently_added(aid, "album")
                # Also save all songs in this album
                for song_obj in album.get("songs", []):
                    song_id = song_obj.get("song_id")
                    if song_id and song_id in self.songs:
                        if not self.songs[song_id].get("saved"):
                            self.songs[song_id]["saved"] = True
                            tracks_added_count += 1
        total = sum(1 for a in self.albums.values() if a.get("saved"))
        return {
            "added_albums": added,
            "already_in_library": already,
            "tracks_added": tracks_added_count,
            "total_library_albums": total,
        }

    def remove_albums_from_library(
        self,
        album_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Remove albums from the current user's personal library. Tracks from
        the album are also removed from the library unless they were
        independently added.

        Args:
            album_ids (List[str]): Album IDs to remove.

        Returns:
            Dict[str, Any]: Result with fields:
                removed (List[str]), not_in_library (List[str]),
                total_library_albums (int).
        """
        removed = []
        not_found = []
        for aid in album_ids:
            album = self.albums.get(aid)
            if album and album.get("saved"):
                album["saved"] = False
                removed.append(aid)
                # Also unsave songs belonging to this album
                for song_obj in album.get("songs", []):
                    song_id = song_obj.get("song_id")
                    if song_id and song_id in self.songs:
                        self.songs[song_id]["saved"] = False
            else:
                not_found.append(aid)
        total = sum(1 for a in self.albums.values() if a.get("saved"))
        return {
            "removed": removed,
            "not_in_library": not_found,
            "total_library_albums": total,
        }

    def get_library_albums(self) -> List[Dict[str, Any]]:
        """
        Get all albums in the current user's personal library with full
        catalog details.

        Returns:
            List[Dict[str, Any]]: List of catalog album objects in the user's library.
        """
        results = []
        for aid, album in self.albums.items():
            if album.get("saved"):
                results.append(deepcopy(album))
        return results

    # -----------------------------------------------------------------------
    # Ratings (love / dislike)
    # -----------------------------------------------------------------------

    def rate_track(
        self,
        track_id: str,
        rating: str,
    ) -> Dict[str, Any]:
        """
        Rate a track as 'love' or 'dislike'. Ratings influence recommendations
        and auto-generated queues. Use rating 'none' to remove a previous rating.

        Args:
            track_id (str): The track to rate.
            rating (str): One of "love", "dislike", or "none" (to clear).

        Returns:
            Dict[str, Any]: Result with fields:
                track_id (str), rating (str), previous_rating (str | None).
        """
        self._require_catalog_track(track_id)
        if rating not in ("love", "dislike", "none"):
            raise AppleMusicError(
                "INVALID_RATING",
                f"Invalid rating '{rating}'. Must be 'love', 'dislike', or 'none'.",
                suggested_action="Use one of: 'love', 'dislike', 'none'.",
                context={"rating": rating},
            )
        previous = self.ratings.get(track_id)
        if rating == "none":
            self.ratings.pop(track_id, None)
        else:
            self.ratings[track_id] = rating
        return {
            "track_id": track_id,
            "rating": rating,
            "previous_rating": previous,
        }

    def get_track_rating(self, track_id: str) -> Dict[str, Any]:
        """
        Get the current user's rating for a specific track.

        Args:
            track_id (str): The track to check.

        Returns:
            Dict[str, Any]: Result with fields:
                track_id (str), rating (str | None). None if not rated.
        """
        rating = self.ratings.get(track_id)
        return {"track_id": track_id, "rating": rating}

    def get_loved_tracks(self) -> List[Dict[str, Any]]:
        """
        Get all tracks the current user has rated as 'love'.

        Returns:
            List[Dict[str, Any]]: List of catalog track objects for loved tracks.
        """
        results = []
        for tid, rating in self.ratings.items():
            if rating == "love":
                t = self.songs.get(tid)
                if t:
                    results.append(deepcopy(t))
        return results

    # -----------------------------------------------------------------------
    # Playlist management
    # -----------------------------------------------------------------------

    def get_library_playlists(self) -> List[Dict[str, Any]]:
        """
        Get all playlists in the current user's library, including playlists
        they own and public playlists they have added.

        Returns:
            List[Dict[str, Any]]: Playlist summaries, each with fields:
                playlist_id (str), name (str), owner_id (str),
                track_count (int), public (bool), description (str).
        """
        results = []
        for p in self.playlists.values():
            if p.get("owner_id") == self.user_id or p.get("public", False):
                song_list = p.get("songs", [])
                results.append(
                    {
                        "playlist_id": p["playlist_id"],
                        "name": p.get("name"),
                        "owner_id": p.get("owner_id"),
                        "track_count": len(song_list),
                        "public": p.get("public", False),
                        "description": p.get("description", ""),
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
                songs (List[Dict]), public (bool), description (str).
        """
        return deepcopy(self._require_playlist(playlist_id))

    def create_playlist(
        self,
        name: str,
        description: str = "",
        is_public: bool = False,
    ) -> str:
        """
        Create a new playlist in the current user's library.

        Args:
            name (str): Display name for the playlist.
            description (str): Optional playlist description. Defaults to "".
            is_public (bool): Whether the playlist is publicly visible. Defaults to False.

        Returns:
            str: The new playlist_id.
        """
        if not name or not name.strip():
            raise AppleMusicError(
                "INVALID_PLAYLIST_NAME",
                "Playlist name cannot be empty.",
                suggested_action="Provide a non-empty playlist name.",
            )
        playlist_id = self._new_id("playlist")
        self.playlists[playlist_id] = {
            "playlist_id": playlist_id,
            "name": name.strip(),
            "owner_id": self.user_id,
            "songs": [],
            "public": is_public,
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
        Add one or more tracks to a playlist. The current user must be the owner.

        Args:
            playlist_id (str): The target playlist.
            track_ids (List[str]): List of catalog track IDs to add.

        Returns:
            Dict[str, Any]: Updated playlist snapshot with fields:
                playlist_id (str), name (str), track_count (int),
                added (List[str]).
        """
        playlist = self._require_playlist(playlist_id)
        if playlist.get("owner_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        if not track_ids:
            raise AppleMusicError(
                "NO_TRACKS_PROVIDED",
                "At least one track_id must be provided.",
                suggested_action="Pass a non-empty list of track_ids.",
            )
        added = []
        for tid in track_ids:
            song = self._require_catalog_track(tid)
            # Append embedded song object to playlist
            playlist.setdefault("songs", []).append({
                "song_id": tid,
                "name": song.get("name", ""),
                "genre": song.get("genre", []),
                "play_count": song.get("play_count", 0),
            })
            added.append(tid)
        return {
            "playlist_id": playlist_id,
            "name": playlist.get("name"),
            "track_count": len(playlist.get("songs", [])),
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
                removed (List[str]).
        """
        playlist = self._require_playlist(playlist_id)
        if playlist.get("owner_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        removed = []
        songs_list = playlist.get("songs", [])
        for tid in track_ids:
            # Find and remove first occurrence by song_id
            for i, song_obj in enumerate(songs_list):
                if song_obj.get("song_id") == tid:
                    songs_list.pop(i)
                    removed.append(tid)
                    break
        return {
            "playlist_id": playlist_id,
            "name": playlist.get("name"),
            "track_count": len(songs_list),
            "removed": removed,
        }

    def update_playlist_details(
        self,
        playlist_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        is_public: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update metadata for a playlist. Only the owner can update details.

        Args:
            playlist_id (str): The target playlist.
            name (str, optional): New display name.
            description (str, optional): New description.
            is_public (bool, optional): New public visibility setting.

        Returns:
            Dict[str, Any]: Updated playlist object.
        """
        playlist = self._require_playlist(playlist_id)
        if playlist.get("owner_id") != self.user_id:
            raise PermissionError("You do not have permission to access this resource.")
        if name is not None:
            if not name.strip():
                raise AppleMusicError(
                    "INVALID_PLAYLIST_NAME",
                    "Playlist name cannot be empty.",
                    suggested_action="Provide a non-empty name.",
                )
            playlist["name"] = name.strip()
        if description is not None:
            playlist["description"] = description
        if is_public is not None:
            playlist["public"] = is_public
        return deepcopy(playlist)

    def delete_playlist(self, playlist_id: str) -> Dict[str, Any]:
        """
        Delete a playlist from the current user's library. Only the owner
        can delete.

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
    # Stations (curated radio)
    # -----------------------------------------------------------------------

    def get_stations(self) -> List[Dict[str, Any]]:
        """
        Get all available Apple Music radio stations.

        Args:
            (none)

        Returns:
            List[Dict[str, Any]]: Station objects, each with fields:
                station_id (str), name (str), description (str), genre (str).
        """
        return [
            {
                "station_id": s["station_id"],
                "name": s.get("name"),
                "description": s.get("description", ""),
                "genre": s.get("genre", ""),
            }
            for s in self.stations.values()
        ]

    def get_station(self, station_id: str) -> Dict[str, Any]:
        """
        Get details for a specific radio station including its track pool.

        Args:
            station_id (str): The unique station identifier.

        Returns:
            Dict[str, Any]: Station object with fields:
                station_id (str), name (str), description (str),
                genre (str), track_pool (List[str]).
        """
        return deepcopy(self._require_station(station_id))

    def play_station(self, station_id: str) -> Dict[str, Any]:
        """
        Start playing a radio station. A random track from the station's pool
        is selected and playback begins. The station's remaining tracks are
        loaded into the queue.

        Args:
            station_id (str): The station to play.

        Returns:
            Dict[str, Any]: Playback state with fields:
                current_song_id (str), station_id (str), is_playing (bool),
                position_ms (int), shuffle (bool), repeat_mode (str).
        """
        station = self._require_station(station_id)
        pool = list(station.get("track_pool", []))
        if not pool:
            raise AppleMusicError(
                "EMPTY_STATION",
                "This station has no tracks in its pool.",
                suggested_action="Choose a different station.",
                context={"station_id": station_id},
            )
        self._rng.shuffle(pool)
        first_track = pool[0]
        remaining = pool[1:]

        self.player["current_song_id"] = first_track
        self.player["station_id"] = station_id
        self.player["position_ms"] = 0
        self.player["is_playing"] = True
        self.player["shuffle"] = True
        self.player["repeat_mode"] = "off"
        self.player["queue_song_ids"] = remaining

        self._record_recently_played(first_track)
        return deepcopy(self.player)

    # -----------------------------------------------------------------------
    # Playback control (account-level, no device concept)
    # -----------------------------------------------------------------------

    def play_track(
        self,
        track_id: str,
    ) -> Dict[str, Any]:
        """
        Start playing a specific catalog track. Playback is at the account level
        (no device selection required, unlike Spotify).

        Args:
            track_id (str): The catalog track to play.

        Returns:
            Dict[str, Any]: Playback state with fields:
                current_song_id (str), station_id (None), position_ms (int),
                is_playing (bool), shuffle (bool), repeat_mode (str).
        """
        self._require_catalog_track(track_id)

        self.player["current_song_id"] = track_id
        self.player["station_id"] = None
        self.player["position_ms"] = 0
        self.player["is_playing"] = True
        # Preserve existing shuffle/repeat settings
        self.player.setdefault("shuffle", False)
        self.player.setdefault("repeat_mode", "off")

        self._record_recently_played(track_id)
        return deepcopy(self.player)

    def play_album(
        self,
        album_id: str,
        track_offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Start playing an album from a specified track offset. Remaining album
        tracks are loaded into the queue.

        Args:
            album_id (str): The catalog album to play.
            track_offset (int): Zero-based index of the track to start from.
                Defaults to 0 (first track).

        Returns:
            Dict[str, Any]: Playback state with fields:
                current_song_id (str), station_id (None), position_ms (int),
                is_playing (bool), shuffle (bool), repeat_mode (str).
        """
        album = self._require_catalog_album(album_id)
        # Get song IDs from embedded songs list
        track_list = [s.get("song_id") for s in album.get("songs", []) if s.get("song_id")]
        if not track_list:
            raise AppleMusicError(
                "EMPTY_ALBUM",
                "This album has no tracks.",
                suggested_action="Choose a different album.",
                context={"album_id": album_id},
            )
        idx = _clamp(int(track_offset), 0, len(track_list) - 1)
        track_id = track_list[idx]

        self.player["current_song_id"] = track_id
        self.player["station_id"] = None
        self.player["position_ms"] = 0
        self.player["is_playing"] = True
        self.player.setdefault("shuffle", False)
        self.player.setdefault("repeat_mode", "off")

        self.player["queue_song_ids"] = list(track_list[idx + 1:])

        self._record_recently_played(track_id)
        return deepcopy(self.player)

    def play_playlist(
        self,
        playlist_id: str,
        track_offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Start playing a playlist from a specified track offset. Remaining
        playlist tracks are loaded into the queue.

        Args:
            playlist_id (str): The playlist to play.
            track_offset (int): Zero-based index of the track to start from.
                Defaults to 0.

        Returns:
            Dict[str, Any]: Playback state with fields:
                current_song_id (str), station_id (None), position_ms (int),
                is_playing (bool), shuffle (bool), repeat_mode (str).
        """
        playlist = self._require_playlist(playlist_id)
        # Get song IDs from embedded songs list
        track_list = [s.get("song_id") for s in playlist.get("songs", []) if s.get("song_id")]
        if not track_list:
            raise AppleMusicError(
                "EMPTY_PLAYLIST",
                "This playlist has no tracks.",
                suggested_action="Add tracks to the playlist first.",
                context={"playlist_id": playlist_id},
            )
        idx = _clamp(int(track_offset), 0, len(track_list) - 1)
        track_id = track_list[idx]

        self.player["current_song_id"] = track_id
        self.player["station_id"] = None
        self.player["position_ms"] = 0
        self.player["is_playing"] = True
        self.player.setdefault("shuffle", False)
        self.player.setdefault("repeat_mode", "off")

        self.player["queue_song_ids"] = list(track_list[idx + 1:])

        self._record_recently_played(track_id)
        return deepcopy(self.player)

    def pause_playback(self) -> Dict[str, Any]:
        """
        Pause playback for the current user.

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        if not self.player.get("current_song_id"):
            raise AppleMusicError(
                "NO_ACTIVE_PLAYBACK",
                "No active playback session found.",
                suggested_action="Start playback first with play_track(), play_album(), or play_station().",
                context={"user_id": self.user_id},
            )
        self.player["is_playing"] = False
        return deepcopy(self.player)

    def resume_playback(self) -> Dict[str, Any]:
        """
        Resume playback for the current user.

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        if not self.player.get("current_song_id"):
            raise AppleMusicError(
                "NO_ACTIVE_PLAYBACK",
                "No active playback session found.",
                suggested_action="Start playback first.",
                context={"user_id": self.user_id},
            )
        self.player["is_playing"] = True
        return deepcopy(self.player)

    def skip_to_next(self) -> Dict[str, Any]:
        """
        Skip to the next track. Tracks are taken from the queue. If the queue
        is empty, playback stops.

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        if not self.player.get("current_song_id") and not self.player.get("is_playing"):
            raise AppleMusicError(
                "NO_ACTIVE_PLAYBACK",
                "No active playback session found.",
                suggested_action="Start playback first.",
                context={"user_id": self.user_id},
            )
        queue = self._ensure_queue()

        if queue:
            next_track = queue.pop(0)
        else:
            self.player["current_song_id"] = None
            self.player["is_playing"] = False
            self.player["position_ms"] = 0
            return deepcopy(self.player)

        self.player["current_song_id"] = next_track
        self.player["position_ms"] = 0
        self.player["station_id"] = None
        self._record_recently_played(next_track)
        return deepcopy(self.player)

    def skip_to_previous(self) -> Dict[str, Any]:
        """
        Skip to the previous track. In this simplified model, if the current
        position is more than 3 seconds in, it restarts the current track.
        Otherwise, the most recent track from recently_played is loaded.

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        if not self.player.get("current_song_id") and not self.player.get("is_playing"):
            raise AppleMusicError(
                "NO_ACTIVE_PLAYBACK",
                "No active playback session found.",
                suggested_action="Start playback first.",
                context={"user_id": self.user_id},
            )
        if self.player.get("position_ms", 0) > 3000:
            self.player["position_ms"] = 0
        else:
            if len(self.recently_played) > 1:
                prev_entry = self.recently_played[1]
                self.player["current_song_id"] = prev_entry.get("track_id")
                self.player["position_ms"] = 0
        return deepcopy(self.player)

    def seek_track(self, position_ms: int) -> Dict[str, Any]:
        """
        Seek to a position in the currently playing track.

        Args:
            position_ms (int): Target position in milliseconds. Must be >= 0.

        Returns:
            Dict[str, Any]: Updated playback state reflecting the new position.
        """
        if not self.player.get("current_song_id"):
            raise AppleMusicError(
                "NO_ACTIVE_PLAYBACK",
                "No active playback session found.",
                suggested_action="Start playback first.",
                context={"user_id": self.user_id},
            )
        pos = max(0, int(position_ms))
        track = self.songs.get(self.player.get("current_song_id", ""))
        if track:
            pos = min(pos, track.get("duration_ms", pos))
        self.player["position_ms"] = pos
        return deepcopy(self.player)

    def set_shuffle(self, state: bool) -> Dict[str, Any]:
        """
        Toggle shuffle mode for the current user's playback.

        Args:
            state (bool): True to enable shuffle, False to disable.

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        if not self.player.get("current_song_id"):
            raise AppleMusicError(
                "NO_ACTIVE_PLAYBACK",
                "No active playback session found.",
                suggested_action="Start playback first.",
                context={"user_id": self.user_id},
            )
        self.player["shuffle"] = bool(state)
        return deepcopy(self.player)

    def set_repeat(self, mode: str) -> Dict[str, Any]:
        """
        Set the repeat mode for the current user's playback.

        Args:
            mode (str): One of "off", "one" (repeat current track), or "all".

        Returns:
            Dict[str, Any]: Updated playback state.
        """
        if mode not in ("off", "one", "all"):
            raise AppleMusicError(
                "INVALID_REPEAT_MODE",
                f"Invalid repeat mode '{mode}'. Must be 'off', 'one', or 'all'.",
                suggested_action="Use one of: 'off', 'one', 'all'.",
                context={"mode": mode},
            )
        if not self.player.get("current_song_id"):
            raise AppleMusicError(
                "NO_ACTIVE_PLAYBACK",
                "No active playback session found.",
                suggested_action="Start playback first.",
                context={"user_id": self.user_id},
            )
        self.player["repeat_mode"] = mode
        return deepcopy(self.player)

    def get_playback_state(self) -> Dict[str, Any]:
        """
        Get the current playback state for the current user.

        Returns:
            Dict[str, Any]: Playback state with fields:
                current_song_id (str | None), station_id (str | None),
                position_ms (int), is_playing (bool), shuffle (bool),
                repeat_mode (str), queue_song_ids (List[str]),
                active_device_id (str | None).
        """
        return deepcopy(self.player)

    # -----------------------------------------------------------------------
    # Up Next queue
    # -----------------------------------------------------------------------

    def add_to_up_next(
        self,
        track_id: str,
        play_next: bool = False,
    ) -> Dict[str, Any]:
        """
        Add a track to the Up Next queue. If play_next is True, the track is
        inserted at the front of the queue. Otherwise it is appended to the end.

        Args:
            track_id (str): The catalog track to enqueue.
            play_next (bool): If True, insert at the front of the queue
                (Play Next). If False, append to the end (Play Later). Defaults
                to False.

        Returns:
            Dict[str, Any]: Queue snapshot with fields:
                queue_length (int), added_track (str),
                position (str, "next" or "later").
        """
        self._require_catalog_track(track_id)
        queue = self._ensure_queue()
        if play_next:
            queue.insert(0, track_id)
            position = "next"
        else:
            queue.append(track_id)
            position = "later"
        return {
            "queue_length": len(queue),
            "added_track": track_id,
            "position": position,
        }

    def get_up_next(self) -> Dict[str, Any]:
        """
        Get the current user's Up Next queue.

        Returns:
            Dict[str, Any]: Queue object with fields:
                queue_song_ids (List[str]): Tracks in the queue.
        """
        queue = self._ensure_queue()
        return {"queue_song_ids": list(queue)}

    def clear_up_next(self, clear_auto: bool = False) -> Dict[str, Any]:
        """
        Clear the Up Next queue.

        Args:
            clear_auto (bool): Ignored in the new flat queue model. The entire
                queue is always cleared. Defaults to False.

        Returns:
            Dict[str, Any]: Confirmation with fields:
                cleared (bool).
        """
        self.player["queue_song_ids"] = []
        return {"cleared": True}

    # -----------------------------------------------------------------------
    # Recently Played & Recently Added
    # -----------------------------------------------------------------------

    def get_recently_played(
        self,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get the current user's recently played tracks, ordered most recent first.

        Args:
            limit (int): Maximum number of entries to return. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Recently played entries, each with:
                track_id (str), played_at (str, ISO-8601 timestamp).
        """
        return deepcopy(self.recently_played[: max(1, int(limit))])

    def get_recently_added(
        self,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Get items recently added to the current user's library, ordered most
        recent first.

        Args:
            limit (int): Maximum number of entries to return. Defaults to 20.

        Returns:
            List[Dict[str, Any]]: Recently added entries, each with:
                item_id (str), item_type (str, "track" or "album"),
                added_at (str, ISO-8601 timestamp).
        """
        return deepcopy(self.recently_added[: max(1, int(limit))])

    # -----------------------------------------------------------------------
    # Social / following
    # -----------------------------------------------------------------------

    def follow_artist(self, artist_id: str) -> Dict[str, Any]:
        """
        Follow an artist on Apple Music.

        Args:
            artist_id (str): The artist to follow.

        Returns:
            Dict[str, Any]: Result with fields:
                followed (bool), artist_id (str), total_followed (int).
        """
        artist = self._require_artist(artist_id)
        if artist.get("following"):
            total = sum(1 for a in self.artists.values() if a.get("following"))
            return {
                "followed": False,
                "artist_id": artist_id,
                "total_followed": total,
                "message": "Already following this artist.",
            }
        artist["following"] = True
        total = sum(1 for a in self.artists.values() if a.get("following"))
        return {
            "followed": True,
            "artist_id": artist_id,
            "total_followed": total,
        }

    def unfollow_artist(self, artist_id: str) -> Dict[str, Any]:
        """
        Unfollow an artist on Apple Music.

        Args:
            artist_id (str): The artist to unfollow.

        Returns:
            Dict[str, Any]: Result with fields:
                unfollowed (bool), artist_id (str), total_followed (int).
        """
        artist = self.artists.get(artist_id)
        if not artist or not artist.get("following"):
            total = sum(1 for a in self.artists.values() if a.get("following"))
            return {
                "unfollowed": False,
                "artist_id": artist_id,
                "total_followed": total,
                "message": "Not currently following this artist.",
            }
        artist["following"] = False
        total = sum(1 for a in self.artists.values() if a.get("following"))
        return {
            "unfollowed": True,
            "artist_id": artist_id,
            "total_followed": total,
        }

    def get_followed_artists(self) -> List[Dict[str, Any]]:
        """
        Get the list of artists the current user is following.

        Returns:
            List[Dict[str, Any]]: List of artist objects for followed artists.
        """
        results = []
        for aid, artist in self.artists.items():
            if artist.get("following"):
                results.append(deepcopy(artist))
        return results

    def share_track(self, track_id: str) -> Dict[str, Any]:
        """
        Generate a shareable link for a track.

        Args:
            track_id (str): The track to share.

        Returns:
            Dict[str, Any]: Result with fields:
                share_url (str), track_id (str), shared_by (str).
        """
        self._require_catalog_track(track_id)
        return {
            "share_url": f"https://music.apple.com/track/{track_id}",
            "track_id": track_id,
            "shared_by": self.user_id,
        }

    # -----------------------------------------------------------------------
    # Account info
    # -----------------------------------------------------------------------

    def get_user_profile(self) -> Dict[str, Any]:
        """
        Get profile information for the current user.

        Returns:
            Dict[str, Any]: User profile with fields:
                user_id (str), name (str), email (str),
                subscription_type (str e.g. "individual", "family", "student"),
                country (str, ISO country code e.g. "US", "GB").
        """
        return {
            "user_id": self.user_id,
            "name": self.profile.get("name"),
            "email": self.profile.get("email"),
            "subscription_type": self.profile.get("subscription_type", "individual"),
            "country": self.profile.get("country", "US"),
        }

    # -----------------------------------------------------------------------
    # Sing Mode (Karaoke)
    # -----------------------------------------------------------------------

    def get_sing_availability(self, track_id: str) -> Dict[str, Any]:
        """
        Check if a track supports Sing mode (Apple Music karaoke).

        Args:
            track_id (str): The track to check.

        Returns:
            Dict[str, Any]: Result with fields:
                track_id (str), available (bool), has_lyrics (bool).
        """
        self._require_catalog_track(track_id)
        sing_info = self.sing_catalog.get(track_id, {})
        available = sing_info.get("available", False)
        has_lyrics = sing_info.get("has_lyrics", False)
        return {
            "track_id": track_id,
            "available": available,
            "has_lyrics": has_lyrics,
        }

    def start_sing_mode(
        self,
        track_id: str,
        vocal_level: int = 50,
    ) -> Dict[str, Any]:
        """
        Start playback of a track in Sing mode with adjustable vocal level.
        A vocal_level of 0 is fully instrumental, 100 is normal vocals.

        Args:
            track_id (str): The track to play in Sing mode.
            vocal_level (int): Vocal level from 0 (instrumental) to 100
                (normal vocals). Defaults to 50.

        Returns:
            Dict[str, Any]: Playback state with fields:
                current_song_id (str), sing_mode (bool), vocal_level (int),
                is_playing (bool), position_ms (int).
        """
        self._require_catalog_track(track_id)
        sing_info = self.sing_catalog.get(track_id, {})
        if not sing_info.get("available", False):
            raise AppleMusicError(
                "SING_NOT_AVAILABLE",
                f"Sing mode is not available for track '{track_id}'.",
                suggested_action="Use get_sing_availability() to check supported tracks.",
                context={"track_id": track_id},
            )

        level = _clamp(int(vocal_level), 0, 100)

        self.player["current_song_id"] = track_id
        self.player["station_id"] = None
        self.player["position_ms"] = 0
        self.player["is_playing"] = True
        self.player["sing_mode"] = True
        self.player["vocal_level"] = level
        self.player.setdefault("shuffle", False)
        self.player.setdefault("repeat_mode", "off")

        self._record_recently_played(track_id)
        return {
            "current_song_id": track_id,
            "sing_mode": True,
            "vocal_level": level,
            "is_playing": True,
            "position_ms": 0,
        }

    def get_lyrics(
        self,
        track_id: str,
        synced: bool = False,
    ) -> Dict[str, Any]:
        """
        Get lyrics for a track, optionally time-synced.

        Args:
            track_id (str): The track whose lyrics to retrieve.
            synced (bool): If True, return time-synced lyrics with start_ms
                and end_ms per line. Defaults to False.

        Returns:
            Dict[str, Any]: Result with fields:
                track_id (str), lyrics (List[Dict] | List[str]),
                synced (bool).
        """
        self._require_catalog_track(track_id)
        sing_info = self.sing_catalog.get(track_id, {})
        if not sing_info.get("has_lyrics", False):
            raise AppleMusicError(
                "LYRICS_NOT_AVAILABLE",
                f"Lyrics are not available for track '{track_id}'.",
                suggested_action="Not all tracks have lyrics available.",
                context={"track_id": track_id},
            )

        raw_lyrics = sing_info.get("lyrics", [])
        if synced:
            # Return time-synced lyrics
            lyrics = []
            for i, line in enumerate(raw_lyrics):
                if isinstance(line, dict):
                    lyrics.append(deepcopy(line))
                else:
                    lyrics.append({
                        "text": str(line),
                        "start_ms": i * 5000,
                        "end_ms": (i + 1) * 5000,
                    })
        else:
            # Return plain text lyrics
            lyrics = []
            for line in raw_lyrics:
                if isinstance(line, dict):
                    lyrics.append(line.get("text", ""))
                else:
                    lyrics.append(str(line))

        return {
            "track_id": track_id,
            "lyrics": lyrics,
            "synced": synced,
        }

    # -----------------------------------------------------------------------
    # Replay (Annual Listening Stats)
    # -----------------------------------------------------------------------

    def get_replay(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Get Apple Music Replay stats for a given year.

        Args:
            year (int, optional): The year to retrieve replay stats for.
                Defaults to the current year.

        Returns:
            Dict[str, Any]: Replay stats with fields:
                year (int), top_artists (List[Dict]), top_albums (List[Dict]),
                top_songs (List[Dict]), total_play_time_hours (int),
                top_genres (List[str]).
        """
        if year is None:
            year = datetime.now(timezone.utc).year

        year_str = str(year)
        if year_str in self.replay:
            return deepcopy(self.replay[year_str])

        # Derive replay from current state
        saved_tracks = [
            deepcopy(s) for s in self.songs.values() if s.get("saved")
        ]
        saved_tracks.sort(key=lambda t: t.get("play_count", 0), reverse=True)

        top_songs = [
            {"song_id": t.get("song_id"), "name": t.get("name", ""), "play_count": t.get("play_count", 0)}
            for t in saved_tracks[:10]
        ]

        # Top genres
        genre_counts: Dict[str, int] = {}
        for t in saved_tracks:
            for g in t.get("genre", []):
                genre_counts[g] = genre_counts.get(g, 0) + 1
        top_genres = sorted(genre_counts.keys(), key=lambda g: genre_counts[g], reverse=True)[:5]

        # Top artists
        artist_counts: Dict[str, int] = {}
        for t in saved_tracks:
            for aid in (t.get("artist_id") or []):
                artist_counts[aid] = artist_counts.get(aid, 0) + 1
        top_artist_ids = sorted(artist_counts.keys(), key=lambda a: artist_counts[a], reverse=True)[:5]
        top_artists = []
        for aid in top_artist_ids:
            artist = self.artists.get(aid)
            if artist:
                top_artists.append({"artist_id": aid, "name": artist.get("name", "")})

        # Top albums
        album_counts: Dict[str, int] = {}
        for t in saved_tracks:
            alb = t.get("album_id")
            if alb:
                album_counts[alb] = album_counts.get(alb, 0) + 1
        top_album_ids = sorted(album_counts.keys(), key=lambda a: album_counts[a], reverse=True)[:5]
        top_albums = []
        for alb_id in top_album_ids:
            album = self.albums.get(alb_id)
            if album:
                top_albums.append({"album_id": alb_id, "name": album.get("name", "")})

        total_ms = sum(
            s.get("duration_ms", 0) * max(1, s.get("play_count", 1))
            for s in saved_tracks
        )
        total_hours = total_ms // 3600000

        return {
            "year": year,
            "top_artists": top_artists,
            "top_albums": top_albums,
            "top_songs": top_songs,
            "total_play_time_hours": total_hours,
            "top_genres": top_genres,
        }

    def get_replay_playlist(self, year: Optional[int] = None) -> Dict[str, Any]:
        """
        Get the auto-generated Replay playlist for a given year.

        Args:
            year (int, optional): The year to retrieve the replay playlist for.
                Defaults to the current year.

        Returns:
            Dict[str, Any]: Replay playlist with fields:
                year (int), playlist_name (str), tracks (List[Dict]).
        """
        if year is None:
            year = datetime.now(timezone.utc).year

        year_str = str(year)

        # Check if there's a pre-seeded replay playlist
        replay_data = self.replay.get(year_str, {})
        if "playlist_tracks" in replay_data:
            return {
                "year": year,
                "playlist_name": f"Replay {year}",
                "tracks": deepcopy(replay_data["playlist_tracks"]),
            }

        # Otherwise derive from saved tracks
        saved_tracks = [
            deepcopy(s) for s in self.songs.values() if s.get("saved")
        ]
        saved_tracks.sort(key=lambda t: t.get("play_count", 0), reverse=True)
        tracks = [
            {"song_id": t.get("song_id"), "name": t.get("name", ""), "play_count": t.get("play_count", 0)}
            for t in saved_tracks[:25]
        ]

        return {
            "year": year,
            "playlist_name": f"Replay {year}",
            "tracks": tracks,
        }

    # -----------------------------------------------------------------------
    # Spatial Audio
    # -----------------------------------------------------------------------

    def get_spatial_audio_status(self) -> Dict[str, Any]:
        """
        Get the current spatial audio status for the user.

        Returns:
            Dict[str, Any]: Status with fields:
                enabled (bool), available (bool).
        """
        enabled = self.audio_settings.get("spatial_audio_enabled", False)
        available = self.audio_settings.get("spatial_audio_available", True)
        return {
            "enabled": enabled,
            "available": available,
        }

    def toggle_spatial_audio(self, enabled: bool) -> Dict[str, Any]:
        """
        Enable or disable spatial audio.

        Args:
            enabled (bool): True to enable spatial audio, False to disable.

        Returns:
            Dict[str, Any]: Updated status with fields:
                enabled (bool), available (bool).
        """
        available = self.audio_settings.get("spatial_audio_available", True)
        if not available and enabled:
            raise AppleMusicError(
                "SPATIAL_AUDIO_UNAVAILABLE",
                "Spatial audio is not available on this device or account.",
                suggested_action="Check device compatibility for spatial audio support.",
            )
        self.audio_settings["spatial_audio_enabled"] = bool(enabled)
        return {
            "enabled": bool(enabled),
            "available": available,
        }

    def get_track_audio_quality(self, track_id: str) -> Dict[str, Any]:
        """
        Get the available audio formats for a track.

        Args:
            track_id (str): The track to check.

        Returns:
            Dict[str, Any]: Result with fields:
                track_id (str), formats (List[str]). Possible formats:
                "standard", "lossless", "hi_res", "dolby_atmos".
        """
        track = self._require_catalog_track(track_id)
        # Check for per-track audio_formats, fall back to default
        formats = track.get("audio_formats")
        if not formats:
            formats = ["standard"]
        return {
            "track_id": track_id,
            "formats": list(formats),
        }
