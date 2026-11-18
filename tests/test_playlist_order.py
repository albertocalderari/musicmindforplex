"""Playlist tempo order stays visible in preview and preserves missing BPM tracks."""

import unittest
from unittest.mock import patch

from musicmind.brain import sequence_for_flow
from web.app import app


class PlaylistOrderTests(unittest.TestCase):
    def setUp(self):
        self.tracks = [
            {"rating_key": "a", "bpm": 120},
            {"rating_key": "b", "bpm": None},
            {"rating_key": "c", "bpm": 80},
            {"rating_key": "d", "bpm": 100},
            {"rating_key": "e", "bpm": 140},
            {"rating_key": "f", "bpm": 90},
        ]

    def keys(self, tracks):
        return [track["rating_key"] for track in tracks]

    def test_bpm_orders(self):
        self.assertEqual(self.keys(sequence_for_flow(self.tracks)), ["c", "d", "e", "a", "f", "b"])
        self.assertEqual(self.keys(sequence_for_flow(self.tracks, "BPM ascending")), ["c", "f", "d", "a", "e", "b"])
        self.assertEqual(self.keys(sequence_for_flow(self.tracks, "BPM descending")), ["e", "a", "d", "f", "c", "b"])
        self.assertEqual(sequence_for_flow(self.tracks, "Best match"), self.tracks)

    def test_preview_uses_selected_order(self):
        with patch("web.app.search_tracks", return_value=self.tracks), patch("web.app.update_query_log_result_count"):
            response = app.test_client().post("/preview", json={"order": "BPM ascending"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.keys(response.get_json()["tracks"]), ["c", "f", "d", "a", "e", "b"])

    def test_invalid_order_is_rejected(self):
        response = app.test_client().post("/preview", json={"order": "shuffle"})
        self.assertEqual(response.status_code, 400)

    def test_date_search_uses_selected_order(self):
        with patch("web.app.get_scrobbled_tracks_around_date", return_value=["a"]), \
             patch("web.app.get_missing_scrobbles_around_date", return_value=[]), \
             patch("web.app.search_tracks", return_value=self.tracks):
            response = app.test_client().post("/onthisday", json={"date": "2026-11-18", "order": "BPM descending"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.keys(response.get_json()["tracks"]), ["e", "a", "d", "f", "c", "b"])

    def test_seed_search_uses_selected_order(self):
        with patch("web.app.find_similar_by_track", return_value=self.tracks), \
             patch("web.app.log_query", return_value=1), \
             patch("web.app.update_query_log_result_count"):
            response = app.test_client().post("/based-on", json={"type": "track", "rating_key": "a", "order": "BPM ascending"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.keys(response.get_json()["tracks"]), ["c", "f", "d", "a", "e", "b"])


if __name__ == "__main__":
    unittest.main()
