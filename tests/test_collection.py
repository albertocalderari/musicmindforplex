"""Collection data semantics, refresh behavior, and pagination."""
import asyncio
import sqlite3
from unittest.mock import patch

import pytest


from musicmind_ui.collection import ranked_rows, timeline_rows
from musicmind_ui.state import UI


def test_timeline_gaps_are_not_zero_and_periods_are_ordered():
    rows = timeline_rows([{'month': '2025-01', 'plays': 0}, {'month': '2024-11', 'plays': 8}], 'month')
    assert [r['period'] for r in rows] == ['2024-11', '2024-12', '2025-01']
    assert rows[1]['plays'] is None
    assert rows[1]['display'] == 'No recorded data'
    assert rows[2]['plays'] == 0
    assert rows[2]['display'] == '0'


def test_rank_bars_use_whole_loaded_set_and_handle_zero():
    rows = ranked_rows([{'artist': 'Long artist', 'plays': 12000}, {'artist': 'Other', 'plays': 3000}], 'artist', 'plays')
    assert rows[1] == dict(name='Other', rank=2, count='3,000', width='25.00%')
    assert ranked_rows([{'artist': 'Zero', 'plays': 0}], 'artist', 'plays')[0]['width'] == '0.00%'


def payload():
    return {'stats': {'total_tracks': 100, 'total_artists': 20, 'total_scrobbles': 4, 'total_instrumental': 0},
            'top_artists': [{'artist': str(i), 'plays': 100-i} for i in range(25)],
            'top_genres': [], 'by_country': [], 'by_gender': [], 'by_era': [],
            'listening_granularity': 'year', 'listening_by_year': [{'year': '2025', 'plays': 4}]}


def test_refresh_failure_keeps_data_and_pagination_is_independent():
    async def check():
        state = UI(_reflex_internal_init=True)
        with patch('musicmind_ui.state._legacy', return_value=payload()):
            async for _ in state.stats_load():
                pass
        state.stats_turn_page('artist', 1)
        assert state.stats_visible['artist'][0]['rank'] == 11
        assert state.stats_pages['genre'] == 0
        state.stats_turn_page('artist', 99)
        assert state.stats_ranges['artist'] == '21–25 of 25 loaded'
        with patch('musicmind_ui.state._legacy', side_effect=RuntimeError('offline')):
            async for _ in state.stats_load():
                pass
        assert state.stats_loaded and not state.stats_loading
        assert 'offline' in state.stats_error
        assert state.stats_display['total_tracks'] == '100'
        with patch('musicmind_ui.state._legacy', return_value=payload()):
            async for _ in state.set_stats_limit('artist', '25'):
                pass
        assert state.stats_pages['artist'] == 0
        assert state.stats_error == ''
    asyncio.run(check())


def test_metadata_counts_only_current_artists_and_includes_missing_gender(tmp_path):
    from web.app import app
    import web.app as backend
    database = tmp_path / 'stats.db'
    with sqlite3.connect(database) as conn:
        conn.executescript('''
            CREATE TABLE tracks (rating_key TEXT, artist TEXT, real_artist TEXT, play_count INTEGER, genre TEXT, is_instrumental INTEGER);
            CREATE TABLE artist_meta (artist TEXT, era TEXT, country TEXT, gender TEXT);
            CREATE TABLE track_tags (rating_key TEXT, tag TEXT);
            CREATE TABLE lastfm_scrobbles (timestamp INTEGER);
            CREATE TABLE itunes_history (library_id TEXT, track_id TEXT, play_count INTEGER, last_played TEXT);
            INSERT INTO itunes_history VALUES ('library','track',100,'2020-01-02T00:00:00+00:00');
            INSERT INTO lastfm_scrobbles VALUES (1577923200);
            INSERT INTO tracks VALUES ('1','Current',NULL,3,'Jazz',0), ('2','Missing',NULL,0,NULL,0);
            INSERT INTO artist_meta VALUES ('Current','1990s','US','unknown'), ('Removed','1980s','GB','male');
        ''')
    with patch.object(backend, 'DB_PATH', str(database)), app.test_client() as client:
        data = client.get('/stats/data').get_json()
    assert data['total_itunes_dated_plays'] == 1
    assert data['itunes_listening_by_year'] == [{'year': '2020', 'plays': 1}]
    assert data['stats']['total_scrobbles'] == 1
    assert data['by_era'] == [{'era': '1990s', 'cnt': 1}]
    assert sum(row['cnt'] for row in data['by_country']) == 1
    assert {r['gender']: r['cnt'] for r in data['by_gender']} == {'unknown': 1, 'Unclassified': 1}


def test_initial_failure_is_not_an_empty_success():
    async def check():
        state = UI(_reflex_internal_init=True)
        with patch('musicmind_ui.state._legacy', side_effect=RuntimeError('offline')):
            async for _ in state.stats_load():
                pass
        assert not state.stats_loaded
        assert not state.stats_loading
        assert state.stats_error
    asyncio.run(check())


def test_late_response_does_not_overwrite_newer_response():
    import threading
    started, release = threading.Event(), threading.Event()
    calls = 0

    def fetch(*args):
        nonlocal calls
        calls += 1
        result = payload()
        if calls == 1:
            started.set()
            assert release.wait(3)
            result['stats']['total_tracks'] = 999
        return result

    async def check():
        state = UI(_reflex_internal_init=True)
        async def load():
            async for _ in state.stats_load():
                pass
        with patch('musicmind_ui.state._legacy', side_effect=fetch):
            first = asyncio.create_task(load())
            await asyncio.to_thread(started.wait, 3)
            await load()
            release.set()
            await first
        assert state.stats_display['total_tracks'] == '100'
        assert not state.stats_loading
    asyncio.run(check())


def test_stats_page_compiles():
    from musicmind_ui.musicmind_ui import app
    app._compile_page('stats')
    from reflex.compiler import compiler
    _, javascript = compiler.compile_page('stats', app._pages['stats'])
    assert 'toLocaleString' in javascript
    assert 'Chart unavailable' in javascript


@pytest.mark.parametrize('limit', ['10', '25', '50', '100'])
def test_all_result_limits_keep_at_most_ten_rows_visible(limit):
    async def check():
        state = UI(_reflex_internal_init=True)
        data = payload()
        data['top_artists'] = [{'artist': 'A very long artist name ' * 8, 'plays': 1000000 - i}
                               for i in range(int(limit))]
        with patch('musicmind_ui.state._legacy', return_value=data):
            async for _ in state.set_stats_limit('artist', limit):
                pass
        seen = []
        for page in range((int(limit) + 9) // 10):
            visible = state.stats_visible['artist']
            assert len(visible) <= 10
            seen.extend(row['rank'] for row in visible)
            state.stats_turn_page('artist', 1)
        assert seen == list(range(1, int(limit) + 1))
    asyncio.run(check())


def test_combined_chart_sums_sources_per_period_without_accumulating():
    state = UI(_reflex_internal_init=True)
    state.stats = {'combined_listening_by_year': [{'year': '2020', 'plays': 3}],
                   'combined_listening_by_month': [{'month': '2020-01', 'plays': 2, 'lastfm': 1, 'plex': 1},
                                                   {'month': '2020-03', 'plays': 1, 'itunes': 1}],
                   'total_known_dated_plays': 3}
    assert [row['plays'] for row in state.listening_rows] == [2, None, 1]
    for row in state.listening_rows:
        if row['plays'] is not None:
            assert sum(row[source] for source in ('lastfm', 'plex', 'itunes')) == row['plays']
    assert state.listening_total == '3'
