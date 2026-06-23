import random
import re
import unicodedata
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError


DEFAULT_LEVELS = [
    (Decimal("0.5"), 100, "0.5 s"),
    (Decimal("1"), 80, "1 s"),
    (Decimal("2"), 60, "2 s"),
    (Decimal("5"), 40, "5 s"),
    (Decimal("10"), 20, "10 s"),
    (Decimal("20"), 10, "więcej"),
]

POLISH_TRANSLATION = str.maketrans(
    {
        "ą": "a",
        "ć": "c",
        "ę": "e",
        "ł": "l",
        "ń": "n",
        "ó": "o",
        "ś": "s",
        "ź": "z",
        "ż": "z",
        "Ą": "A",
        "Ć": "C",
        "Ę": "E",
        "Ł": "L",
        "Ń": "N",
        "Ó": "O",
        "Ś": "S",
        "Ź": "Z",
        "Ż": "Z",
    }
)


def default_levels_text():
    return "\n".join(f"{seconds:g}:{points}" for seconds, points, _label in DEFAULT_LEVELS)


def parse_levels_definition(raw_value):
    if raw_value is None:
        raise ValidationError("Podaj poziomy odsłuchu.")

    normalized_lines = raw_value.replace(",", "\n").splitlines()
    levels = []

    for line_number, raw_line in enumerate(normalized_lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        if ":" not in line:
            raise ValidationError(
                f"Poziom w linii {line_number} musi mieć format czas:punkty, np. 0.5:100."
            )

        seconds_raw, points_raw = [part.strip().replace("s", "") for part in line.split(":", 1)]
        try:
            seconds = Decimal(seconds_raw)
        except InvalidOperation as exc:
            raise ValidationError(f"Czas w linii {line_number} nie jest poprawną liczbą.") from exc

        try:
            points = int(points_raw)
        except ValueError as exc:
            raise ValidationError(f"Punkty w linii {line_number} muszą być liczbą całkowitą.") from exc

        if seconds <= 0:
            raise ValidationError(f"Czas w linii {line_number} musi być większy od zera.")
        if points < 0:
            raise ValidationError(f"Punkty w linii {line_number} nie mogą być ujemne.")

        levels.append((seconds, points))

    if not levels:
        raise ValidationError("Dodaj co najmniej jeden poziom odsłuchu.")

    return levels


def normalize_answer(value):
    text = (value or "").translate(POLISH_TRANSLATION)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(character for character in text if not unicodedata.combining(character))
    text = text.lower()
    text = re.sub(r"\((feat\.?|ft\.?|with|remaster|radio edit|edit|version).*?\)", " ", text)
    text = re.sub(r"\[(feat\.?|ft\.?|with|remaster|radio edit|edit|version).*?\]", " ", text)
    text = re.sub(r"\s+-\s+(remaster|radio edit|edit|version).*?$", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def answers_match(user_guess, correct_title):
    guess = normalize_answer(user_guess)
    correct = normalize_answer(correct_title)
    return bool(guess) and guess == correct


def representative_start_ms(duration_ms, listen_seconds):
    if not duration_ms:
        return 0

    listen_ms = int(Decimal(str(listen_seconds)) * 1000)
    safe_tail_ms = 10000
    if duration_ms <= listen_ms + safe_tail_ms:
        return 0

    preferred_start = max(15000, duration_ms // 3)
    latest_start = max(0, duration_ms - listen_ms - safe_tail_ms)
    return min(preferred_start, latest_start)


def select_tracks_for_game(tracks, rounds_count):
    if rounds_count < 1:
        raise ValueError("Liczba rund musi być większa od zera.")
    if not tracks:
        raise ValueError("Nie można rozpocząć gry bez utworów.")
    selected_count = min(len(tracks), rounds_count)
    return random.sample(tracks, selected_count)


def level_to_session(level):
    return {
        "id": level.id,
        "order": level.order,
        "listen_seconds": float(level.listen_seconds),
        "points": level.points,
        "label": level.display_label,
    }
