from django import forms

from .gameplay import default_levels_text, parse_levels_definition
from .models import GameMode


class GameModeForm(forms.ModelForm):
    levels_definition = forms.CharField(
        label="Poziomy odsłuchu",
        help_text="Wpisz jeden poziom w linii w formacie czas:punkty, np. 0.5:100.",
        initial=default_levels_text,
        widget=forms.Textarea(attrs={"rows": 6}),
    )

    class Meta:
        model = GameMode
        fields = ["name", "description", "rounds_count", "max_attempts", "is_default", "is_active"]
        labels = {
            "name": "Nazwa",
            "description": "Opis",
            "rounds_count": "Liczba rund",
            "max_attempts": "Liczba prób",
            "is_default": "Ustaw jako domyślny",
            "is_active": "Aktywny",
        }

    def clean_levels_definition(self):
        raw_value = self.cleaned_data["levels_definition"]
        self.cleaned_data["parsed_levels"] = parse_levels_definition(raw_value)
        return raw_value


class StartGameForm(forms.Form):
    playlist_id = forms.CharField(max_length=255)
    playlist_name = forms.CharField(max_length=255, required=False)
    playlist_image_url = forms.URLField(required=False)
    game_mode_id = forms.IntegerField(required=False)


class GuessForm(forms.Form):
    guess = forms.CharField(max_length=255, required=False)
    action = forms.ChoiceField(
        choices=(("guess", "Zgaduję"), ("skip", "Nie wiem")),
        required=False,
    )
