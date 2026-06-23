from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_default_mode(apps, schema_editor):
    GameMode = apps.get_model("quiz", "GameMode")
    ListeningLevel = apps.get_model("quiz", "ListeningLevel")

    GameMode.objects.filter(is_default=True).update(is_default=False)
    mode, _created = GameMode.objects.get_or_create(
        name="Klasyczny",
        defaults={
            "description": "Domyślna rozgrywka z rosnącym czasem odsłuchu po błędnych próbach.",
            "rounds_count": 5,
            "max_attempts": 3,
            "is_active": True,
        },
    )
    mode.description = "Domyślna rozgrywka z rosnącym czasem odsłuchu po błędnych próbach."
    mode.rounds_count = 5
    mode.max_attempts = 3
    mode.is_default = True
    mode.is_active = True
    mode.save()

    levels = [
        (Decimal("0.5"), 100, "0.5 s"),
        (Decimal("1"), 80, "1 s"),
        (Decimal("2"), 60, "2 s"),
        (Decimal("5"), 40, "5 s"),
        (Decimal("10"), 20, "10 s"),
        (Decimal("20"), 10, "więcej"),
    ]
    for order, (seconds, points, label) in enumerate(levels, start=1):
        ListeningLevel.objects.update_or_create(
            game_mode=mode,
            order=order,
            defaults={
                "listen_seconds": seconds,
                "points": points,
                "label": label,
            },
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GameMode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True, verbose_name="nazwa")),
                ("description", models.TextField(blank=True, verbose_name="opis")),
                (
                    "rounds_count",
                    models.PositiveSmallIntegerField(
                        default=5,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(50),
                        ],
                        verbose_name="liczba rund",
                    ),
                ),
                (
                    "max_attempts",
                    models.PositiveSmallIntegerField(
                        default=3,
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(10),
                        ],
                        verbose_name="liczba prób",
                    ),
                ),
                ("is_default", models.BooleanField(default=False, verbose_name="tryb domyślny")),
                ("is_active", models.BooleanField(default=True, verbose_name="aktywny")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="utworzono")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="zaktualizowano")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="created_game_modes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="autor",
                    ),
                ),
            ],
            options={
                "verbose_name": "tryb gry",
                "verbose_name_plural": "tryby gry",
                "ordering": ["-is_default", "name"],
            },
        ),
        migrations.CreateModel(
            name="ListeningLevel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "order",
                    models.PositiveSmallIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="kolejność",
                    ),
                ),
                (
                    "listen_seconds",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=5,
                        validators=[django.core.validators.MinValueValidator(0.1)],
                        verbose_name="czas odsłuchu",
                    ),
                ),
                (
                    "points",
                    models.PositiveIntegerField(
                        validators=[django.core.validators.MinValueValidator(0)],
                        verbose_name="punkty",
                    ),
                ),
                ("label", models.CharField(blank=True, max_length=40, verbose_name="etykieta")),
                (
                    "game_mode",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="levels",
                        to="quiz.gamemode",
                        verbose_name="tryb gry",
                    ),
                ),
            ],
            options={
                "verbose_name": "poziom odsłuchu",
                "verbose_name_plural": "poziomy odsłuchu",
                "ordering": ["order"],
            },
        ),
        migrations.CreateModel(
            name="GameResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("playlist_id", models.CharField(max_length=255, verbose_name="ID playlisty Spotify")),
                ("playlist_name", models.CharField(max_length=255, verbose_name="nazwa playlisty")),
                ("score", models.PositiveIntegerField(default=0, verbose_name="wynik")),
                ("max_possible_score", models.PositiveIntegerField(default=0, verbose_name="maksymalny wynik")),
                (
                    "rounds_count",
                    models.PositiveSmallIntegerField(
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="liczba rund",
                    ),
                ),
                ("correct_answers", models.PositiveSmallIntegerField(default=0, verbose_name="poprawne odpowiedzi")),
                ("details", models.JSONField(blank=True, default=list, verbose_name="szczegóły rund")),
                ("played_at", models.DateTimeField(auto_now_add=True, verbose_name="data gry")),
                (
                    "game_mode",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="results",
                        to="quiz.gamemode",
                        verbose_name="tryb gry",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="game_results",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="użytkownik",
                    ),
                ),
            ],
            options={
                "verbose_name": "wynik gry",
                "verbose_name_plural": "wyniki gier",
                "ordering": ["-score", "-correct_answers", "played_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="listeninglevel",
            constraint=models.UniqueConstraint(fields=("game_mode", "order"), name="unique_level_order_per_mode"),
        ),
        migrations.AddIndex(
            model_name="gameresult",
            index=models.Index(fields=["game_mode", "playlist_id", "-score"], name="quiz_result_mode_list_score"),
        ),
        migrations.AddIndex(
            model_name="gameresult",
            index=models.Index(fields=["user", "game_mode", "playlist_id", "-score"], name="quiz_result_user_mode_score"),
        ),
        migrations.RunPython(create_default_mode, migrations.RunPython.noop),
    ]
