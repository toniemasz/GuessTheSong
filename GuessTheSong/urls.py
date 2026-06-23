"""
URL configuration for GuessThatSong project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from . import views  # upewnij się, że importujesz swoje widoki

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='home'),
    path('login/', views.login_spotify, name='login'),
    path('callback/', views.callback, name='callback'),
    path('game-modes/new/', views.create_game_mode, name='create_game_mode'),
    path('playlists/<int:game_mode_id>/', views.choose_playlist, name='choose_playlist'),
    path('view-playlist/', views.view_playlist, name='view_playlist'),
    path('start-game/', views.start_game, name='start_game'),
    path('game/round/', views.game_round, name='game_round'),
    path('game/next/', views.next_round, name='next_round'),
    path('game/summary/<int:result_id>/', views.game_summary, name='game_summary'),
    path('ranking/', views.ranking, name='ranking'),
    path('check-guess/', views.check_guess, name='check_guess'),
]
