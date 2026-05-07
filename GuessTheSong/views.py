import random
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.conf import settings
import spotipy
from .game_logic import PlaylistManager, Game
from .spotify_service import create_spotify_oauth, get_spotify_client


def index(request):
    sp = get_spotify_client(request)
    if not sp:
        return render(request, 'login.html')

    try:
        results = sp.current_user_playlists(limit=None)
        user = sp.current_user()
        return render(request, 'choosePlaylist.html', {
            'playlists': results['items'],
            'user_name': user['display_name']
        })
    except Exception as e:
        print(f"BŁĄD: {e}")
        request.session.clear()
        return render(request, 'login.html')


def login_spotify(request):
    auth_manager = create_spotify_oauth()
    auth_url = auth_manager.get_authorize_url()
    return redirect(auth_url)

def callback(request):
    auth_manager = create_spotify_oauth()
    code = request.GET.get('code')
    if code:
        try:
            token_info = auth_manager.get_access_token(code)
            request.session['token_info'] = token_info
            return redirect('home')
        except Exception as e:
            print(f"BŁĄD W CALLBACK: {e}")
    return redirect('home')


def view_playlist(request):
    if request.method == 'POST':
        playlist_id = request.POST.get('playlist_id')

        sp = get_spotify_client(request)
        if not sp:
            return redirect('home')

        manager = PlaylistManager(sp)
        tracks = manager.get_all_tracks(playlist_id)

        return render(request, 'allSongsInPlaylist.html', {
            'tracks': tracks,
            'total_tracks': len(tracks)
        })
    return redirect('home')


def start_game(request):
    if request.method == 'POST':
        sp = get_spotify_client(request)
        if not sp:
            return redirect('home')

        playlist_id = request.POST.get('playlist_id')
        game = Game(playlist_id, sp)
        random_track = game.get_random_track()

        request.session['correct_track'] = {
            'name': random_track.name,
            'artist': random_track.artist
        }

        return render(request, 'game.html', {
            'track_uri': random_track.uri,
            'spotify_token': request.session['token_info']['access_token'],
            'track_names': game.get_all_tracks_names(),
            'difficulty_name': "Normalny",
            'current_time_ms': 5000
        })
    return redirect('home')


from django.http import JsonResponse


def check_guess(request):
    user_guess = request.GET.get('guess', '').strip().lower()

    correct_data = request.session.get('correct_track')

    if not correct_data:
        return JsonResponse({
            'result': 'error',
            'message': 'Sesja wygasła. Odśwież stronę główną.'
        }, status=400)

    correct_name = correct_data.get('name', '').strip().lower()

    if user_guess == correct_name:
        return JsonResponse({
            'result': 'correct',
            'message': f"Brawo! To faktycznie '{correct_data['name']}'!"
        })

    return JsonResponse({
        'result': 'wrong',
        'message': "To nie to! Próbuj dalej..."
    })