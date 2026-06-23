from django.contrib import admin

from .models import GameMode, GameResult, ListeningLevel


class ListeningLevelInline(admin.TabularInline):
    model = ListeningLevel
    extra = 1
    min_num = 1


@admin.register(GameMode)
class GameModeAdmin(admin.ModelAdmin):
    list_display = ("name", "rounds_count", "max_attempts", "is_default", "is_active", "created_by")
    list_filter = ("is_default", "is_active")
    search_fields = ("name", "description")
    inlines = [ListeningLevelInline]


@admin.register(GameResult)
class GameResultAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "game_mode",
        "playlist_name",
        "score",
        "correct_answers",
        "rounds_count",
        "played_at",
    )
    list_filter = ("game_mode", "playlist_name", "played_at")
    search_fields = ("user__username", "playlist_name", "playlist_id")
    readonly_fields = ("played_at",)
