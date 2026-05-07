import random


class Track:
    """Klasa reprezentująca pojedynczą piosenkę."""

    def __init__(self, track_id, name, artist, uri):
        self.id = track_id
        self.name = name
        self.artist = artist
        self.uri = uri

    def __str__(self):
        return f"{self.artist} - {self.name}"


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
            raw_tracks.extend(results.get('items', []))

            while results.get('next'):
                results = self.sp.next(results)
                raw_tracks.extend(results.get('items', []))

        except Exception as e:
            print(f"Błąd komunikacji z API: {e}")
            return []

        track_objects = []
        for element in raw_tracks:
            if not isinstance(element, dict):
                continue

            track_data = element.get('track') or element.get('item')

            if not track_data or not isinstance(track_data, dict):
                continue

            if not track_data.get('id'):
                continue

            new_track = Track(
                track_id=track_data['id'],
                name=track_data.get('name', 'Nieznany tytuł'),
                artist=track_data['artists'][0]['name'] if track_data.get('artists') else 'Nieznany artysta',
                uri=track_data.get('uri', '')
            )
            track_objects.append(new_track)


        return track_objects


import random

class Game:
    def __init__(self, playlist_id, sp):
        self.playlist_id = playlist_id
        self.sp = sp
        self.tracks = self._load_tracks()

    def _load_tracks(self):
        results = self.sp.playlist_items(self.playlist_id)
        tracks = []

        for item in results.get('items', []):
            if not isinstance(item, dict):
                continue

            track = item.get('track') or item.get('item')

            if not track or not isinstance(track, dict):
                continue

            if not track.get('id'):
                continue

            tracks.append({
                'name': track.get('name', 'Nieznany tytuł'),
                'artist': track['artists'][0]['name'] if track.get('artists') else 'Nieznany artysta',
                'uri': track.get('uri', '')
            })

        return tracks

    def get_random_track(self):
        track = random.choice(self.tracks)
        return type('Track', (), track)

    def get_all_tracks_names(self):
        return [track['name'] for track in self.tracks]