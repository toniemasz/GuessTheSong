import time
import logging

import spotipy
from spotipy import SpotifyOAuth
from spotipy.cache_handler import MemoryCacheHandler
from spotipy.exceptions import SpotifyException

from . import settings


logger = logging.getLogger(__name__)

SPOTIFY_SCOPES = (
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-read-private",
    "user-read-email",
    "streaming",
    "user-read-playback-state",
    "user-modify-playback-state",
)
SPOTIFY_SCOPE = " ".join(SPOTIFY_SCOPES)


def missing_token_scopes(token_info, required_scopes=SPOTIFY_SCOPES):
    granted_scopes = set((token_info or {}).get("scope", "").split())
    return set(required_scopes) - granted_scopes


def get_spotify_client(request):
    token_info = request.session.get('token_info')

    if not token_info:
        return None

    missing_scopes = missing_token_scopes(token_info)
    if missing_scopes:
        logger.warning("Sesja Spotify ma brakujące uprawnienia: %s.", ", ".join(sorted(missing_scopes)))
        request.session.clear()
        return None

    now = int(time.time())
    expires_at = token_info.get('expires_at')
    refresh_token = token_info.get('refresh_token')

    if expires_at is None:
        logger.warning("Sesja Spotify nie zawiera czasu wygaśnięcia tokena.")
        request.session.clear()
        return None

    if expires_at - now < 60:
        if not refresh_token:
            logger.warning("Sesja Spotify nie zawiera refresh tokena.")
            request.session.clear()
            return None
        auth_manager = create_spotify_oauth()
        try:
            token_info = auth_manager.refresh_access_token(refresh_token)
            request.session['token_info'] = token_info
        except SpotifyException as exc:
            logger.exception("Nie udało się odświeżyć tokena Spotify.")
            request.session.clear()
            return None

    return spotipy.Spotify(auth=token_info['access_token'])

def create_spotify_oauth():
    '''
    This function creates a SpotifyOAuth object with the necessary settings from settings.py.
    :return: SpotifyOAuth
    '''
    return SpotifyOAuth(
        client_id=settings.CLIENT_ID,
        client_secret=settings.CLIENT_SECRET,
        redirect_uri=settings.REDIRECT_URI,
        scope=SPOTIFY_SCOPE,
        cache_handler=MemoryCacheHandler(),
        show_dialog=True
    )
