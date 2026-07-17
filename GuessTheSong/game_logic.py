import logging
import random

from spotipy.exceptions import SpotifyException


logger = logging.getLogger(__name__)


class PlaylistLoadError(Exception):
    """Raised when tracks cannot be loaded from Spotify."""


class Track:
    """Klasa reprezentująca pojedynczą piosenkę."""

    def __init__(self, track_id, name, artist, uri, duration_ms=None, image_url="", album_name=""):
        self.id = track_id
        self.name = name
        self.artist = artist
        self.uri = uri
        self.duration_ms = duration_ms
        self.image_url = image_url
        self.album_name = album_name

    def __str__(self):
        return f"{self.artist} - {self.name}"

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "artist": self.artist,
            "uri": self.uri,
            "duration_ms": self.duration_ms,
            "image_url": self.image_url,
            "album_name": self.album_name,
        }


class PlaylistManager:
    """Klasa do obsługi Spotify API."""

    def __init__(self, sp_client):
        self.sp = sp_client

    def get_random_track(self, playlist_id):
        tracks = self.get_all_tracks(playlist_id)
        if not tracks:
            return None
        return random.choice(tracks)

    def get_all_tracks(self, playlist_id):
        raw_tracks = []

        try:
            results = self.sp.playlist_items(playlist_id)
            raw_tracks.extend(results.get("items", []))

            while results.get("next"):
                results = self.sp.next(results)
                raw_tracks.extend(results.get("items", []))
        except SpotifyException as exc:
            logger.exception("Spotify API nie zwróciło utworów dla playlisty %s.", playlist_id)
            raise PlaylistLoadError("Nie udało się pobrać utworów z wybranej playlisty.") from exc

        track_objects = []
        for element in raw_tracks:
            if not isinstance(element, dict):
                logger.warning("Pominięto nieoczekiwany element playlisty: %r", element)
                continue

            track_data = element.get("track") or element.get("item")
            if not track_data or not isinstance(track_data, dict):
                logger.warning("Pominięto element playlisty bez danych utworu: %r", element)
                continue

            track_id = track_data.get("id")
            if not track_id:
                logger.info("Pominięto utwór bez ID Spotify: %r", track_data.get("name"))
                continue

            artists = track_data.get("artists") or []
            album = track_data.get("album") or {}
            images = album.get("images") or []
            image_url = images[0].get("url", "") if images and isinstance(images[0], dict) else ""
            uri = track_data.get("uri") or f"spotify:track:{track_id}"
            track_objects.append(
                Track(
                    track_id=track_id,
                    name=track_data.get("name", "Nieznany tytuł"),
                    artist=artists[0]["name"] if artists else "Nieznany artysta",
                    uri=uri,
                    duration_ms=track_data.get("duration_ms"),
                    image_url=image_url,
                    album_name=album.get("name", ""),
                )
            )

        return track_objects


class Game:
    def __init__(self, playlist_id, sp):
        self.playlist_id = playlist_id
        self.sp = sp
        self.tracks = self._load_tracks()

    def _load_tracks(self):
        return PlaylistManager(self.sp).get_all_tracks(self.playlist_id)

    def get_random_track(self):
        if not self.tracks:
            raise PlaylistLoadError("Wybrana playlista nie ma dostępnych utworów.")
        return random.choice(self.tracks)

    def get_all_tracks_names(self):
        return [track.name for track in self.tracks]
