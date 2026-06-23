from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from quiz.gameplay import answers_match, level_to_session, representative_start_ms
from quiz.models import GameMode, GameResult, ListeningLevel


class GameplayUtilityTests(TestCase):
    def test_answer_matching_ignores_case_accents_and_common_version_suffixes(self):
        self.assertTrue(answers_match("zolte kalendarze", "Żółte Kalendarze"))
        self.assertTrue(answers_match("Song Title", "Song Title (Radio Edit)"))
        self.assertFalse(answers_match("Different Song", "Song Title"))

    def test_representative_start_keeps_enough_time_before_track_end(self):
        self.assertEqual(representative_start_ms(None, Decimal("1")), 0)
        self.assertEqual(representative_start_ms(9000, Decimal("1")), 0)
        self.assertEqual(representative_start_ms(180000, Decimal("2")), 60000)


class GameRoundFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="spotify_test", password="secret")
        self.mode = GameMode.objects.create(name="Test mode", rounds_count=1, max_attempts=3, is_active=True)
        self.level_1 = ListeningLevel.objects.create(
            game_mode=self.mode,
            order=1,
            listen_seconds=Decimal("0.50"),
            points=100,
            label="0.5 s",
        )
        self.level_2 = ListeningLevel.objects.create(
            game_mode=self.mode,
            order=2,
            listen_seconds=Decimal("1.00"),
            points=80,
            label="1 s",
        )
        self.client.force_login(self.user)

    def _put_game_state_in_session(self):
        session = self.client.session
        session["game_state"] = {
            "game_mode_id": self.mode.pk,
            "game_mode_name": self.mode.name,
            "playlist_id": "playlist-1",
            "playlist_name": "Test playlist",
            "playlist_image_url": "",
            "rounds_total": 1,
            "max_attempts": 3,
            "levels": [level_to_session(self.level_1), level_to_session(self.level_2)],
            "tracks": [
                {
                    "id": "track-1",
                    "name": "Perfect Song",
                    "artist": "The Band",
                    "uri": "spotify:track:track-1",
                    "duration_ms": 180000,
                }
            ],
            "track_names": ["Perfect Song"],
            "current_round_index": 0,
            "current_attempts": 0,
            "current_level_index": 0,
            "round_answered": False,
            "score": 0,
            "correct_answers": 0,
            "max_possible_score": 100,
            "rounds": [],
        }
        session.save()

    def test_wrong_guess_consumes_attempt_and_moves_to_next_level(self):
        self._put_game_state_in_session()

        response = self.client.post(reverse("check_guess"), {"action": "guess", "guess": "Wrong"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["result"], "wrong")
        self.assertEqual(payload["attempts_left"], 2)
        self.assertEqual(payload["level"]["label"], "1 s")

        state = self.client.session["game_state"]
        self.assertEqual(state["current_attempts"], 1)
        self.assertEqual(state["current_level_index"], 1)
        self.assertFalse(state["round_answered"])

    def test_correct_guess_scores_points_and_next_round_saves_result(self):
        self._put_game_state_in_session()

        response = self.client.post(reverse("check_guess"), {"action": "guess", "guess": "perfect song"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["result"], "correct")
        self.assertEqual(payload["score"], 100)

        next_response = self.client.get(reverse("next_round"))
        self.assertEqual(next_response.status_code, 302)
        self.assertEqual(GameResult.objects.count(), 1)

        result = GameResult.objects.get()
        self.assertEqual(result.user, self.user)
        self.assertEqual(result.game_mode, self.mode)
        self.assertEqual(result.playlist_id, "playlist-1")
        self.assertEqual(result.score, 100)
        self.assertEqual(result.correct_answers, 1)
        self.assertEqual(result.rounds_count, 1)

        summary_response = self.client.get(next_response["Location"])
        self.assertEqual(summary_response.status_code, 200)
        self.assertContains(summary_response, "100 pkt")

        ranking_response = self.client.get(reverse("ranking"))
        self.assertEqual(ranking_response.status_code, 200)
        self.assertContains(ranking_response, "Test playlist")
