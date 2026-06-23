from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from spotipy.exceptions import SpotifyException

from quiz.forms import GameModeForm, GuessForm, StartGameForm
from quiz.gameplay import answers_match, level_to_session, representative_start_ms, select_tracks_for_game
from quiz.models import GameMode, GameResult, ListeningLevel

from .game_logic import PlaylistLoadError, PlaylistManager
from .spotify_service import create_spotify_oauth, get_spotify_client


def _sync_spotify_user(request, sp):
    spotify_user = sp.current_user()
    spotify_id = spotify_user.get("id")
    if not spotify_id:
        raise ValueError("Spotify nie zwróciło identyfikatora użytkownika.")

    display_name = spotify_user.get("display_name") or spotify_id
    email = spotify_user.get("email") or ""
    username = f"spotify_{spotify_id}"[:150]
    token_info = request.session.get("token_info")

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "first_name": display_name[:150],
            "email": email,
        },
    )
    if created:
        user.set_unusable_password()

    changed_fields = []
    if user.first_name != display_name[:150]:
        user.first_name = display_name[:150]
        changed_fields.append("first_name")
    if email and user.email != email:
        user.email = email
        changed_fields.append("email")
    if created or changed_fields:
        user.save()

    if not request.user.is_authenticated or request.user.pk != user.pk:
        auth_login(request, user)
        if token_info is not None:
            request.session["token_info"] = token_info

    request.session["spotify_user"] = {
        "id": spotify_id,
        "display_name": display_name,
    }
    return spotify_user


def _require_spotify_user(request):
    sp = get_spotify_client(request)
    if not sp:
        return None, None

    if request.user.is_authenticated and request.session.get("spotify_user"):
        return sp, request.session["spotify_user"]

    try:
        spotify_user = _sync_spotify_user(request, sp)
    except SpotifyException:
        messages.error(request, "Nie udało się pobrać danych konta Spotify. Zaloguj się ponownie.")
        request.session.clear()
        return None, None
    except ValueError as exc:
        messages.error(request, str(exc))
        request.session.clear()
        return None, None

    return sp, {
        "id": spotify_user.get("id"),
        "display_name": spotify_user.get("display_name") or spotify_user.get("id"),
    }


def _playlist_image_url(playlist):
    images = playlist.get("images") or []
    if images and isinstance(images[0], dict):
        return images[0].get("url", "")
    return ""


def _load_user_playlists(sp):
    playlists = []
    results = sp.current_user_playlists(limit=50)
    playlists.extend(results.get("items", []))

    while results.get("next"):
        results = sp.next(results)
        playlists.extend(results.get("items", []))

    return playlists


def _get_playlist_snapshot(sp, playlist_id, fallback_name="", fallback_image=""):
    if fallback_name:
        return fallback_name, fallback_image

    playlist = sp.playlist(playlist_id, fields="name,images")
    return playlist.get("name") or "Wybrana playlista", _playlist_image_url(playlist)


def _get_active_mode_or_default(mode_id):
    if mode_id:
        try:
            return GameMode.objects.prefetch_related("levels").get(pk=mode_id, is_active=True)
        except (GameMode.DoesNotExist, TypeError, ValueError):
            return None
    return GameMode.get_default()


def _current_track(state):
    index = state["current_round_index"]
    tracks = state["tracks"]
    if index < 0 or index >= len(tracks):
        raise ValueError("Stan gry wskazuje nieistniejącą rundę.")
    return tracks[index]


def _current_level(state):
    index = state["current_level_index"]
    levels = state["levels"]
    if index < 0 or index >= len(levels):
        raise ValueError("Stan gry wskazuje nieistniejący poziom odsłuchu.")
    return levels[index]


def _round_timing(track, level):
    listen_ms = int(level["listen_seconds"] * 1000)
    start_ms = representative_start_ms(track.get("duration_ms"), level["listen_seconds"])
    return listen_ms, start_ms


def _finish_round(state, status, guess, points, attempts_used, level):
    track = _current_track(state)
    if status == "correct":
        state["score"] += points
        state["correct_answers"] += 1

    state["round_answered"] = True
    state["rounds"].append(
        {
            "round": state["current_round_index"] + 1,
            "track_name": track["name"],
            "artist": track["artist"],
            "guess": guess,
            "status": status,
            "points": points,
            "attempts_used": attempts_used,
            "level_label": level["label"],
            "level_seconds": level["listen_seconds"],
        }
    )


def _round_complete_payload(state, result, message):
    track = _current_track(state)
    return {
        "result": result,
        "message": message,
        "round_complete": True,
        "score": state["score"],
        "correct_answer": track["name"],
        "correct_artist": track["artist"],
        "next_url": "/game/next/",
    }


def _finish_game(request, state):
    if not request.user.is_authenticated:
        raise PermissionDenied("Wynik można zapisać tylko dla zalogowanego użytkownika.")

    game_mode = GameMode.objects.get(pk=state["game_mode_id"])
    result = GameResult.objects.create(
        user=request.user,
        game_mode=game_mode,
        playlist_id=state["playlist_id"],
        playlist_name=state["playlist_name"],
        score=state["score"],
        max_possible_score=state["max_possible_score"],
        rounds_count=state["rounds_total"],
        correct_answers=state["correct_answers"],
        details=state["rounds"],
    )
    request.session["last_game_result_id"] = result.pk
    request.session.pop("game_state", None)
    return result


def index(request):
    sp, spotify_user = _require_spotify_user(request)
    if not sp:
        return render(request, "login.html")

    modes = GameMode.objects.filter(is_active=True).prefetch_related("levels")
    if not modes.exists():
        messages.error(request, "Brakuje aktywnego trybu gry. Dodaj tryb w panelu administratora.")

    return render(
        request,
        "chooseGameMode.html",
        {
            "modes": modes,
            "user_name": spotify_user["display_name"],
        },
    )


def login_spotify(request):
    auth_manager = create_spotify_oauth()
    auth_url = auth_manager.get_authorize_url()
    return redirect(auth_url)


def callback(request):
    auth_manager = create_spotify_oauth()
    code = request.GET.get("code")
    if code:
        try:
            token_info = auth_manager.get_access_token(code)
            request.session["token_info"] = token_info
            return redirect("home")
        except SpotifyException:
            messages.error(request, "Spotify odrzuciło logowanie. Spróbuj ponownie.")
    return redirect("home")


def create_game_mode(request):
    sp, _spotify_user = _require_spotify_user(request)
    if not sp:
        return redirect("home")

    if request.method == "POST":
        form = GameModeForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                mode = form.save(commit=False)
                mode.created_by = request.user if request.user.is_authenticated else None
                mode.save()
                for order, (seconds, points) in enumerate(form.cleaned_data["parsed_levels"], start=1):
                    ListeningLevel.objects.create(
                        game_mode=mode,
                        order=order,
                        listen_seconds=seconds,
                        points=points,
                        label=f"{seconds:g} s",
                    )
            messages.success(request, "Tryb gry został zapisany.")
            if mode.is_active:
                return redirect("choose_playlist", game_mode_id=mode.pk)
            return redirect("home")
    else:
        form = GameModeForm(initial={"is_active": True})

    return render(request, "gameModeForm.html", {"form": form})


def choose_playlist(request, game_mode_id):
    sp, spotify_user = _require_spotify_user(request)
    if not sp:
        return redirect("home")

    game_mode = get_object_or_404(GameMode.objects.prefetch_related("levels"), pk=game_mode_id, is_active=True)

    try:
        playlists = _load_user_playlists(sp)
    except SpotifyException:
        messages.error(request, "Nie udało się pobrać playlist ze Spotify.")
        playlists = []

    return render(
        request,
        "choosePlaylist.html",
        {
            "playlists": playlists,
            "user_name": spotify_user["display_name"],
            "game_mode": game_mode,
        },
    )


def view_playlist(request):
    if request.method != "POST":
        return redirect("home")

    playlist_id = request.POST.get("playlist_id")
    game_mode_id = request.POST.get("game_mode_id")
    playlist_name = request.POST.get("playlist_name", "")
    playlist_image_url = request.POST.get("playlist_image_url", "")

    if not playlist_id:
        messages.error(request, "Nie wybrano playlisty.")
        return redirect("home")

    sp, _spotify_user = _require_spotify_user(request)
    if not sp:
        return redirect("home")

    manager = PlaylistManager(sp)
    try:
        tracks = manager.get_all_tracks(playlist_id)
    except PlaylistLoadError as exc:
        messages.error(request, str(exc))
        return redirect("home")

    game_mode = _get_active_mode_or_default(game_mode_id)
    return render(
        request,
        "allSongsInPlaylist.html",
        {
            "tracks": tracks,
            "total_tracks": len(tracks),
            "playlist_id": playlist_id,
            "playlist_name": playlist_name,
            "playlist_image_url": playlist_image_url,
            "game_mode": game_mode,
        },
    )


def start_game(request):
    if request.method != "POST":
        return redirect("home")

    sp, _spotify_user = _require_spotify_user(request)
    if not sp:
        return redirect("home")

    form = StartGameForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Nie udało się rozpocząć gry. Wybierz playlistę jeszcze raz.")
        return redirect("home")

    mode = _get_active_mode_or_default(form.cleaned_data.get("game_mode_id"))
    if not mode:
        messages.error(request, "Brakuje aktywnego trybu gry.")
        return redirect("home")

    levels = list(mode.levels.order_by("order"))
    if not levels:
        messages.error(request, "Wybrany tryb gry nie ma poziomów odsłuchu.")
        return redirect("home")

    playlist_id = form.cleaned_data["playlist_id"]
    playlist_name = form.cleaned_data.get("playlist_name", "")
    playlist_image_url = form.cleaned_data.get("playlist_image_url", "")

    try:
        playlist_name, playlist_image_url = _get_playlist_snapshot(
            sp,
            playlist_id,
            fallback_name=playlist_name,
            fallback_image=playlist_image_url,
        )
        tracks = PlaylistManager(sp).get_all_tracks(playlist_id)
    except SpotifyException:
        messages.error(request, "Nie udało się pobrać danych playlisty ze Spotify.")
        return redirect("home")
    except PlaylistLoadError as exc:
        messages.error(request, str(exc))
        return redirect("home")

    playable_tracks = [track for track in tracks if track.uri]
    try:
        selected_tracks = select_tracks_for_game(playable_tracks, mode.rounds_count)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("home")

    if len(selected_tracks) < mode.rounds_count:
        messages.warning(
            request,
            f"Playlista ma mniej utworów niż ustawiona liczba rund. Gra potrwa {len(selected_tracks)} rund.",
        )

    session_levels = [level_to_session(level) for level in levels]
    max_points_per_round = max(level.points for level in levels)
    request.session["game_state"] = {
        "game_mode_id": mode.pk,
        "game_mode_name": mode.name,
        "playlist_id": playlist_id,
        "playlist_name": playlist_name,
        "playlist_image_url": playlist_image_url,
        "rounds_total": len(selected_tracks),
        "max_attempts": mode.max_attempts,
        "levels": session_levels,
        "tracks": [track.to_dict() for track in selected_tracks],
        "track_names": sorted({track.name for track in tracks}),
        "current_round_index": 0,
        "current_attempts": 0,
        "current_level_index": 0,
        "round_answered": False,
        "score": 0,
        "correct_answers": 0,
        "max_possible_score": len(selected_tracks) * max_points_per_round,
        "rounds": [],
    }
    return redirect("game_round")


def game_round(request):
    state = request.session.get("game_state")
    if not state:
        messages.info(request, "Rozpocznij nową grę, wybierając tryb i playlistę.")
        return redirect("home")

    try:
        track = _current_track(state)
        level = _current_level(state)
    except ValueError as exc:
        messages.error(request, str(exc))
        request.session.pop("game_state", None)
        return redirect("home")

    token_info = request.session.get("token_info") or {}
    spotify_token = token_info.get("access_token")
    if not spotify_token:
        messages.error(request, "Sesja Spotify wygasła. Zaloguj się ponownie.")
        request.session.pop("game_state", None)
        return redirect("home")

    listen_ms, start_ms = _round_timing(track, level)
    current_round_number = state["current_round_index"] + 1
    progress_rounds = current_round_number if state["round_answered"] else current_round_number - 1
    progress_percent = round((progress_rounds / state["rounds_total"]) * 100)

    return render(
        request,
        "game.html",
        {
            "state": state,
            "track": track,
            "track_uri": track["uri"],
            "spotify_token": spotify_token,
            "track_names": state["track_names"],
            "current_level": level,
            "listen_ms": listen_ms,
            "start_ms": start_ms,
            "attempts_left": state["max_attempts"] - state["current_attempts"],
            "round_number": current_round_number,
            "progress_percent": progress_percent,
        },
    )


def check_guess(request):
    if request.method == "POST":
        form = GuessForm(request.POST)
    else:
        form = GuessForm({"guess": request.GET.get("guess", ""), "action": request.GET.get("action", "guess")})

    if not form.is_valid():
        return JsonResponse(
            {
                "result": "error",
                "message": "Odpowiedź jest niepoprawna technicznie. Spróbuj jeszcze raz.",
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    state = request.session.get("game_state")
    if not state:
        return _legacy_check_guess(request, form.cleaned_data.get("guess", ""))

    if state.get("round_answered"):
        return JsonResponse(
            {
                "result": "error",
                "message": "Ta runda jest już zakończona. Przejdź do kolejnej.",
                "next_url": "/game/next/",
            },
            status=409,
        )

    action = form.cleaned_data.get("action") or "guess"
    guess = (form.cleaned_data.get("guess") or "").strip()

    try:
        track = _current_track(state)
        level = _current_level(state)
    except ValueError as exc:
        return JsonResponse({"result": "error", "message": str(exc)}, status=400)

    if action == "skip":
        _finish_round(state, "skipped", "", 0, state["current_attempts"], level)
        request.session["game_state"] = state
        return JsonResponse(
            _round_complete_payload(
                state,
                "skipped",
                f"Poprawna odpowiedź: {track['artist']} - {track['name']}.",
            )
        )

    if not guess:
        return JsonResponse(
            {
                "result": "validation_error",
                "message": "Wpisz tytuł albo wybierz „Nie wiem”.",
            },
            status=400,
        )

    attempts_used = state["current_attempts"] + 1
    state["current_attempts"] = attempts_used

    if answers_match(guess, track["name"]):
        _finish_round(state, "correct", guess, level["points"], attempts_used, level)
        request.session["game_state"] = state
        return JsonResponse(
            _round_complete_payload(
                state,
                "correct",
                f"Brawo! To {track['artist']} - {track['name']}. Zdobywasz {level['points']} pkt.",
            )
        )

    if attempts_used >= state["max_attempts"]:
        _finish_round(state, "failed", guess, 0, attempts_used, level)
        request.session["game_state"] = state
        return JsonResponse(
            _round_complete_payload(
                state,
                "failed",
                f"Koniec prób. Poprawna odpowiedź: {track['artist']} - {track['name']}.",
            )
        )

    state["current_level_index"] = min(state["current_level_index"] + 1, len(state["levels"]) - 1)
    next_level = _current_level(state)
    listen_ms, start_ms = _round_timing(track, next_level)
    request.session["game_state"] = state
    return JsonResponse(
        {
            "result": "wrong",
            "message": "To nie ten tytuł. Dostajesz dłuższy fragment.",
            "round_complete": False,
            "score": state["score"],
            "attempts_left": state["max_attempts"] - state["current_attempts"],
            "level": next_level,
            "listen_ms": listen_ms,
            "start_ms": start_ms,
        }
    )


def _legacy_check_guess(request, user_guess):
    correct_data = request.session.get("correct_track")
    if not correct_data:
        return JsonResponse(
            {
                "result": "error",
                "message": "Sesja wygasła. Odśwież stronę główną.",
            },
            status=400,
        )

    if answers_match(user_guess, correct_data.get("name", "")):
        return JsonResponse(
            {
                "result": "correct",
                "message": f"Brawo! To faktycznie '{correct_data['name']}'!",
            }
        )

    return JsonResponse(
        {
            "result": "wrong",
            "message": "To nie to! Próbuj dalej...",
        }
    )


def next_round(request):
    state = request.session.get("game_state")
    if not state:
        return redirect("home")

    if not state.get("round_answered"):
        messages.info(request, "Najpierw zakończ aktualną rundę.")
        return redirect("game_round")

    state["current_round_index"] += 1
    if state["current_round_index"] >= state["rounds_total"]:
        result = _finish_game(request, state)
        return redirect("game_summary", result_id=result.pk)

    state["current_attempts"] = 0
    state["current_level_index"] = 0
    state["round_answered"] = False
    request.session["game_state"] = state
    return redirect("game_round")


def game_summary(request, result_id):
    if not request.user.is_authenticated:
        return redirect("home")

    result = get_object_or_404(GameResult.objects.select_related("game_mode", "user"), pk=result_id)
    if result.user_id != request.user.id:
        raise PermissionDenied("Możesz oglądać tylko własne podsumowanie gry.")

    best_result = (
        GameResult.objects.filter(
            user=request.user,
            game_mode=result.game_mode,
            playlist_id=result.playlist_id,
        )
        .order_by("-score", "-correct_answers", "played_at")
        .first()
    )
    rank_position = (
        GameResult.objects.filter(
            game_mode=result.game_mode,
            playlist_id=result.playlist_id,
            score__gt=result.score,
        ).count()
        + 1
    )

    return render(
        request,
        "summary.html",
        {
            "result": result,
            "best_result": best_result,
            "rank_position": rank_position,
        },
    )


def ranking(request):
    if not request.user.is_authenticated:
        messages.info(request, "Zaloguj się przez Spotify, aby zobaczyć ranking.")
        return redirect("home")

    selected_mode_id = request.GET.get("mode")
    selected_playlist_id = request.GET.get("playlist")
    modes = GameMode.objects.filter(is_active=True).order_by("name")
    playlist_choices = (
        GameResult.objects.order_by("playlist_name")
        .values("playlist_id", "playlist_name")
        .distinct()
    )

    results = GameResult.objects.select_related("user", "game_mode")
    if selected_mode_id:
        try:
            results = results.filter(game_mode_id=int(selected_mode_id))
        except ValueError:
            messages.warning(request, "Wybrany filtr trybu gry jest niepoprawny.")
    if selected_playlist_id:
        results = results.filter(playlist_id=selected_playlist_id)

    top_results = results.order_by("-score", "-correct_answers", "played_at")[:20]
    user_results = results.filter(user=request.user).order_by("-score", "-correct_answers", "played_at")[:10]

    return render(
        request,
        "ranking.html",
        {
            "modes": modes,
            "playlist_choices": playlist_choices,
            "selected_mode_id": selected_mode_id,
            "selected_playlist_id": selected_playlist_id,
            "top_results": top_results,
            "user_results": user_results,
        },
    )
