import time
import spotipy
from django.shortcuts import redirect
from spotipy import SpotifyOAuth
from . import settings


def get_spotify_client(request):
    token_info = request.session.get('token_info')

    if not token_info:
        return None

    now = int(time.time())

    if token_info['expires_at'] - now < 60:
        auth_manager = create_spotify_oauth()
        try:
            token_info = auth_manager.refresh_access_token(token_info['refresh_token'])
            request.session['token_info'] = token_info
        except:
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
        scope='playlist-read-private playlist-read-collaborative user-read-private',
        show_dialog=True
    )
