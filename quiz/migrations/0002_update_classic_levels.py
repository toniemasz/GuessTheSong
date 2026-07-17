from decimal import Decimal

from django.db import migrations


CLASSIC_LEVELS = [
    (Decimal("1"), 100, "1 s"),
    (Decimal("2"), 90, "2 s"),
    (Decimal("3"), 80, "3 s"),
    (Decimal("5"), 65, "5 s"),
    (Decimal("8"), 50, "8 s"),
    (Decimal("12"), 35, "12 s"),
    (Decimal("20"), 20, "20 s"),
    (Decimal("30"), 10, "30 s"),
]


def update_classic_levels(apps, schema_editor):
    GameMode = apps.get_model("quiz", "GameMode")
    ListeningLevel = apps.get_model("quiz", "ListeningLevel")

    mode, _created = GameMode.objects.get_or_create(
        name="Klasyczny",
        defaults={
            "description": "Domyślna rozgrywka z rosnącym czasem odsłuchu po błędnych próbach.",
            "rounds_count": 5,
            "max_attempts": len(CLASSIC_LEVELS),
            "is_default": True,
            "is_active": True,
        },
    )
    mode.description = "Domyślna rozgrywka z rosnącym czasem odsłuchu po błędnych próbach."
    mode.max_attempts = len(CLASSIC_LEVELS)
    mode.is_default = True
    mode.is_active = True
    mode.save()
    GameMode.objects.exclude(pk=mode.pk).filter(is_default=True).update(is_default=False)

    ListeningLevel.objects.filter(game_mode=mode).exclude(order__in=range(1, len(CLASSIC_LEVELS) + 1)).delete()
    for order, (seconds, points, label) in enumerate(CLASSIC_LEVELS, start=1):
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
    dependencies = [
        ("quiz", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(update_classic_levels, migrations.RunPython.noop),
    ]
