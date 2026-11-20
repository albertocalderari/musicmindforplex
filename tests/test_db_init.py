"""The CLI creates the complete schema on a fresh local database."""

import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABLES = {
    "meta",
    "tracks",
    "track_tags",
    "artist_meta",
    "track_audio_features",
    "synapse_errors",
    "query_log",
    "lastfm_scrobbles",
    "lastfm_loved",
    "lastfm_meta",
    "artist_gaps",
    "mb_unmatched_artists",
    "track_fingerprints",
    "va_results",
    "vi_results",
    "track_sessions",
    "track_cooccurrence",
    "genre_snapshot",
}


class DatabaseInitTests(unittest.TestCase):
    def test_creates_all_tables_and_can_run_again(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "musicmind.db"
            (root / "config.py").write_text(
                f"BASE_DIR = {str(root)!r}\n"
                f"DB_PATH = {str(database)!r}\n"
                'PLEX_URL = "http://localhost:32400"\n'
                'PLEX_TOKEN = "test-token"\n'
                'MUSIC_LIB = "Music"\n'
                'OPENAI_KEY = "test-key"\n'
                'LASTFM_KEY = ""\n'
                'LASTFM_USER = ""\n'
                'PATH_MAP = {}\n'
                'IS_MASTER = False\n'
            )
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(PROJECT_ROOT)
            for _ in range(2):
                result = subprocess.run(
                    [sys.executable, "-m", "musicmind_cli", "db", "init"],
                    cwd=root,
                    env=environment,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)

            conn = sqlite3.connect(database)
            try:
                tables = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
                }
                self.assertEqual(tables - {"sqlite_sequence"}, TABLES)
                artist_columns = {
                    row[1] for row in conn.execute("PRAGMA table_info(artist_meta)")
                }
                fingerprint_columns = {
                    row[1]
                    for row in conn.execute("PRAGMA table_info(track_fingerprints)")
                }
                self.assertIn("mb_country_checked_at", artist_columns)
                self.assertTrue(
                    {"mbid_check_status", "mbid_checked_at"} <= fingerprint_columns
                )
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
