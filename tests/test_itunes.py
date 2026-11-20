"""iTunes aggregate history remains idempotent across uploads and syncs."""
import plistlib
import sqlite3
from datetime import datetime

import pytest

from musicmind.db.schema import init_all
from musicmind.itunes import apply_history, import_library


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'library.db'
    with sqlite3.connect(path) as conn:
        init_all(conn)
        conn.execute("INSERT INTO tracks (rating_key,artist,title,album,play_count) VALUES ('1','Artist','Song','Album',4)")
    return str(path)


def export(**updates):
    track = {'Persistent ID': 'TRACK1', 'Artist': 'Artist', 'Name': 'Song',
             'Album': 'Album', 'Play Count': 12, 'Play Date UTC': datetime(2020, 1, 2)}
    track.update(updates)
    return plistlib.dumps({'Library Persistent ID': 'LIB1', 'Tracks': {'1': track}})


def test_repeated_import_and_sync_preserve_counts(database):
    for _ in range(2):
        assert import_library(export(), database) == {'imported': 1, 'matched': 1, 'skipped': 0}
    with sqlite3.connect(database) as conn:
        assert conn.execute('SELECT COUNT(*) FROM itunes_history').fetchone()[0] == 1
        assert conn.execute('SELECT play_count,last_played FROM tracks').fetchone() == (12, '2020-01-02T00:00:00+00:00')
        conn.execute("UPDATE tracks SET play_count=3, last_played=NULL")
        apply_history(conn)
        assert conn.execute('SELECT play_count FROM tracks').fetchone()[0] == 12
        conn.execute('UPDATE tracks SET play_count=20')
        apply_history(conn)
        assert conn.execute('SELECT play_count FROM tracks').fetchone()[0] == 20


def test_unmatched_records_rematch_after_ingest(database):
    result = import_library(export(Artist='New Artist'), database)
    assert result['matched'] == 0
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO tracks (rating_key,artist,title,album) VALUES ('2','New Artist','Song','Album')")
        apply_history(conn)
        assert conn.execute("SELECT play_count FROM tracks WHERE rating_key='2'").fetchone()[0] == 12


def test_ambiguous_album_not_matched(database):
    with sqlite3.connect(database) as conn:
        conn.execute("INSERT INTO tracks (rating_key,artist,title,album) VALUES ('2','Artist','Song','Album')")
    assert import_library(export(), database)['matched'] == 0


def test_invalid_export_and_bad_track(database):
    with pytest.raises(ValueError, match='XML'):
        import_library(b'not a library', database)
    with pytest.raises(ValueError, match='Tracks'):
        import_library(plistlib.dumps({'Tracks': {}}), database)
    assert import_library(export(**{'Play Count': -1}), database)['skipped'] == 1


@pytest.mark.parametrize('valid', [True, False])
def test_reflex_upload_handler(database, monkeypatch, valid):
    import asyncio
    import io
    from types import SimpleNamespace
    import reflex as rx
    from musicmind_ui.state import UI

    monkeypatch.setattr('musicmind_ui.state.DB_PATH', database)
    state = SimpleNamespace(itunes_importing=False, itunes_result='')
    upload = rx.UploadFile(file=io.BytesIO(export() if valid else b'invalid'))

    async def run():
        async for _ in UI.import_itunes.fn(state, [upload]):
            pass

    asyncio.run(run())
    assert state.itunes_importing is False
    assert upload.file.closed
    assert ('Imported 1 tracks' if valid else 'Import failed:') in state.itunes_result


@pytest.mark.parametrize('rating,computed,expected', [(80, False, 8), (100, True, None), (0, False, None)])
def test_star_ratings(database, rating, computed, expected):
    import_library(export(**{'Rating': rating, 'Rating Computed': computed}), database)
    with sqlite3.connect(database) as conn:
        assert conn.execute('SELECT user_rating FROM tracks').fetchone()[0] == expected


def test_preserves_existing_local_rating(database):
    with sqlite3.connect(database) as conn:
        conn.execute('UPDATE tracks SET user_rating=6')
    import_library(export(Rating=100), database)
    with sqlite3.connect(database) as conn:
        assert conn.execute('SELECT user_rating FROM tracks').fetchone()[0] == 6


def test_plex_rating_sync_preserves_plex_corrections(database):
    from unittest.mock import Mock
    from musicmind.itunes import sync_ratings_to_plex
    import_library(export(Rating=80), database)
    plex = Mock()
    track = plex.fetchItem.return_value
    track.userRating = None
    assert sync_ratings_to_plex(database, plex)['synced'] == 1
    track.rate.assert_called_once_with(8)
    track.rate.reset_mock()
    track.userRating = 6
    assert sync_ratings_to_plex(database, plex)['refreshed'] == 1
    track.rate.assert_not_called()
    with sqlite3.connect(database) as conn:
        assert conn.execute('SELECT user_rating FROM tracks').fetchone()[0] == 6
    track.rate.reset_mock()
    track.userRating = 6
    assert sync_ratings_to_plex(database, plex)['unchanged'] == 1
    track.rate.assert_not_called()


def test_plex_sync_without_itunes_import(database):
    from unittest.mock import Mock
    from musicmind.itunes import sync_ratings_to_plex
    with sqlite3.connect(database) as conn:
        conn.execute('UPDATE tracks SET user_rating=6')
    plex = Mock()
    plex.fetchItem.return_value.userRating = None
    assert sync_ratings_to_plex(database, plex)['synced'] == 1
    plex.fetchItem.return_value.rate.assert_called_once_with(6)


def test_dated_history_keeps_observed_dates_without_inventing_aggregate_plays(database):
    from musicmind.itunes import listening_history
    import_library(export(), database)
    import_library(export(), database)
    import_library(export(**{'Play Count': 50, 'Play Date UTC': datetime(2021, 5, 6)}), database)
    # Reimporting an older snapshot neither duplicates dates nor removes newer ones.
    import_library(export(), database)
    with sqlite3.connect(database) as conn:
        history = listening_history(conn)
    assert history['total'] == 2
    assert history['year'] == [{'year': '2020', 'plays': 1}, {'year': '2021', 'plays': 1}]
    assert len(history['month']) == 2


def test_existing_imports_are_read_without_reimport_or_schema_mutation():
    from musicmind.itunes import listening_history
    with sqlite3.connect(':memory:') as conn:
        assert listening_history(conn) == {'year': [], 'month': [], 'total': 0}
        conn.executescript('''CREATE TABLE itunes_history (
            library_id TEXT, track_id TEXT, play_count INTEGER, last_played TEXT);
            INSERT INTO itunes_history VALUES ('lib','1',200,'2020-01-02T00:00:00+00:00'),
                ('lib','2',4,NULL), ('lib','3',0,'2020-01-03T00:00:00+00:00'),
                ('lib','4',2,'bad date');''')
        assert listening_history(conn)['total'] == 1
        assert not conn.execute("SELECT name FROM sqlite_master WHERE name='itunes_play_events'").fetchone()


@pytest.mark.parametrize('incremental', [True, False])
def test_ingest_pulls_plex_rating_correction_for_existing_tracks(database, incremental):
    from unittest.mock import Mock
    from musicmind.ingest import ingest, set_last_ingest
    from types import SimpleNamespace
    import_library(export(Rating=100), database)
    track = SimpleNamespace(ratingKey='1', title='Song', userRating=6,
                            addedAt=datetime(2020, 1, 1), lastViewedAt=None,
                            duration=200000, viewCount=1, ratingCount=1)
    album = SimpleNamespace(title='Album', year=2020, tracks=lambda: [track])
    artist = SimpleNamespace(title='Artist', genres=[], albums=lambda: [album])
    plex = Mock()
    plex.library.section.return_value.searchArtists.return_value = [artist]
    with sqlite3.connect(database) as conn:
        if incremental:
            set_last_ingest(conn, '2025-01-01T00:00:00')
        ingest(conn, plex)
        assert conn.execute('SELECT user_rating FROM tracks').fetchone()[0] == 6
        apply_history(conn)
        assert conn.execute('SELECT user_rating FROM tracks').fetchone()[0] == 6


@pytest.mark.parametrize('existing,expected', [(None, 10), (0, 10), (6, 6), (10, 10)])
def test_lastfm_loved_tracks_only_fill_unrated_tracks(database, existing, expected):
    from musicmind.lastfm.sync import update_loved_ratings
    with sqlite3.connect(database) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS lastfm_loved (rating_key TEXT)')
        conn.execute("INSERT INTO lastfm_loved (rating_key) VALUES ('1')")
        conn.execute('UPDATE tracks SET user_rating=?', (existing,))
        update_loved_ratings(conn)
        assert conn.execute('SELECT user_rating FROM tracks').fetchone()[0] == expected


def test_plex_sync_imports_rating_even_when_database_is_unrated(database):
    from unittest.mock import Mock
    from musicmind.itunes import sync_ratings_to_plex
    plex = Mock()
    plex.fetchItem.return_value.userRating = 4
    result = sync_ratings_to_plex(database, plex)
    assert result['refreshed'] == 1
    plex.fetchItem.return_value.rate.assert_not_called()
    with sqlite3.connect(database) as conn:
        assert conn.execute('SELECT user_rating FROM tracks').fetchone()[0] == 4
