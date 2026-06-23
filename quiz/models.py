from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class GameMode(models.Model):
    name = models.CharField("nazwa", max_length=120, unique=True)
    description = models.TextField("opis", blank=True)
    rounds_count = models.PositiveSmallIntegerField(
        "liczba rund",
        default=5,
        validators=[MinValueValidator(1), MaxValueValidator(50)],
    )
    max_attempts = models.PositiveSmallIntegerField(
        "liczba prób",
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
    )
    is_default = models.BooleanField("tryb domyślny", default=False)
    is_active = models.BooleanField("aktywny", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="autor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_game_modes",
    )
    created_at = models.DateTimeField("utworzono", auto_now_add=True)
    updated_at = models.DateTimeField("zaktualizowano", auto_now=True)

    class Meta:
        ordering = ["-is_default", "name"]
        verbose_name = "tryb gry"
        verbose_name_plural = "tryby gry"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            GameMode.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)

    def __str__(self):
        return self.name

    @classmethod
    def get_default(cls):
        default_mode = cls.objects.filter(is_default=True, is_active=True).first()
        if default_mode:
            return default_mode
        return cls.objects.filter(is_active=True).order_by("name").first()


class ListeningLevel(models.Model):
    game_mode = models.ForeignKey(
        GameMode,
        verbose_name="tryb gry",
        on_delete=models.CASCADE,
        related_name="levels",
    )
    order = models.PositiveSmallIntegerField("kolejność", validators=[MinValueValidator(1)])
    listen_seconds = models.DecimalField(
        "czas odsłuchu",
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0.1)],
    )
    points = models.PositiveIntegerField("punkty", validators=[MinValueValidator(0)])
    label = models.CharField("etykieta", max_length=40, blank=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["game_mode", "order"], name="unique_level_order_per_mode"),
        ]
        verbose_name = "poziom odsłuchu"
        verbose_name_plural = "poziomy odsłuchu"

    def __str__(self):
        return f"{self.game_mode}: {self.display_label} za {self.points} pkt"

    @property
    def display_label(self):
        if self.label:
            return self.label
        seconds = float(self.listen_seconds)
        if seconds.is_integer():
            return f"{int(seconds)} s"
        return f"{seconds:g} s"


class GameResult(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="użytkownik",
        on_delete=models.CASCADE,
        related_name="game_results",
    )
    game_mode = models.ForeignKey(
        GameMode,
        verbose_name="tryb gry",
        on_delete=models.PROTECT,
        related_name="results",
    )
    playlist_id = models.CharField("ID playlisty Spotify", max_length=255)
    playlist_name = models.CharField("nazwa playlisty", max_length=255)
    score = models.PositiveIntegerField("wynik", default=0)
    max_possible_score = models.PositiveIntegerField("maksymalny wynik", default=0)
    rounds_count = models.PositiveSmallIntegerField("liczba rund", validators=[MinValueValidator(1)])
    correct_answers = models.PositiveSmallIntegerField("poprawne odpowiedzi", default=0)
    details = models.JSONField("szczegóły rund", default=list, blank=True)
    played_at = models.DateTimeField("data gry", auto_now_add=True)

    class Meta:
        ordering = ["-score", "-correct_answers", "played_at"]
        indexes = [
            models.Index(fields=["game_mode", "playlist_id", "-score"], name="quiz_result_mode_list_score"),
            models.Index(fields=["user", "game_mode", "playlist_id", "-score"], name="quiz_result_user_mode_score"),
        ]
        verbose_name = "wynik gry"
        verbose_name_plural = "wyniki gier"

    def __str__(self):
        return f"{self.user} - {self.score} pkt ({self.game_mode}, {self.playlist_name})"
