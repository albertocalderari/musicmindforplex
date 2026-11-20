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
