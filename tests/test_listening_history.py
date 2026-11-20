"""Combined history sums labelled sources and excludes matching cross-source plays."""
from datetime import datetime, timezone
import sqlite3
from types import SimpleNamespace

from musicmind.listening import combined_history
from musicmind.plex.history import sync_history


def test_combined_history_deduplicates_sources_but_preserves_repeats():
    with sqlite3.connect(':memory:') as conn:
        conn.executescript('''
            CREATE TABLE lastfm_scrobbles (timestamp INTEGER, artist TEXT, title TEXT, rating_key TEXT);
            CREATE TABLE plex_play_events (timestamp INTEGER, artist TEXT, title TEXT, rating_key TEXT);
            CREATE TABLE itunes_history (library_id TEXT, track_id TEXT, play_count INTEGER,
                last_played TEXT, artist TEXT, title TEXT, rating_key TEXT);
            INSERT INTO lastfm_scrobbles VALUES
                (1577923200,'Artist','Song','1'), (1577923500,'Artist','Song','1');
            INSERT INTO plex_play_events VALUES
                (1577923230,'Artist','Song','1'), (1577923800,'Artist','Song','1'),
                (1577923200,'Other','Song','2');
            INSERT INTO itunes_history VALUES
                ('lib','1',500,'2020-01-02T00:00:00+00:00',' artist ','song',NULL),
                ('lib','3',100,'2010-01-02T00:00:00+00:00','Old','Song',NULL);
        ''')
        result = combined_history(conn)
    assert result['total'] == 5
    assert result['sources'] == {'lastfm': 2, 'plex': 2, 'itunes': 1}
    assert result['duplicates'] == 2
    assert result['year'][0]['year'] == '2010'
    for row in result['month']:
        assert row['plays'] == sum(row[source] for source in ('lastfm', 'plex', 'itunes'))


def test_no_sources_is_successfully_empty():
    with sqlite3.connect(':memory:') as conn:
        assert combined_history(conn)['total'] == 0


def test_plex_sync_filters_account_and_library_and_is_idempotent(tmp_path):
    from unittest.mock import Mock
    plex = Mock(machineIdentifier='server')
    plex.library.section.return_value.key = 7
    def event(key, year, kind='track'):
        return SimpleNamespace(historyKey=key, viewedAt=datetime(year, 1, 2, tzinfo=timezone.utc),
                               type=kind, ratingKey='1', grandparentTitle='Artist', title='Song')
    plex.history.return_value = [event('/history/1', 2010), event('/history/2', 2020),
                                 event('/history/3', 2020, 'movie')]
    database = str(tmp_path / 'history.db')
    assert sync_history(plex, database, 'Music')['added'] == 2
    assert sync_history(plex, database, 'Music')['added'] == 0
    plex.history.assert_called_with(librarySectionID=7, accountID=1)
    with sqlite3.connect(database) as conn:
        result = combined_history(conn)
    assert result['total'] == 2
    assert result['year'][0]['year'] == '2010'


def test_plex_sync_failure_does_not_create_partial_history(tmp_path):
    from unittest.mock import Mock
    import pytest
    plex = Mock()
    plex.history.side_effect = RuntimeError('unavailable')
    database = tmp_path / 'history.db'
    with pytest.raises(RuntimeError):
        sync_history(plex, str(database), 'Music')
    assert not database.exists()
