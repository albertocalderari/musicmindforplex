"""Combine known dated listens without allocating undated lifetime totals."""
from bisect import bisect_left
from collections import defaultdict
from datetime import datetime
import sqlite3


def combined_history(conn: sqlite3.Connection) -> dict:
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    def columns(table):
        return {r[1] for r in conn.execute(f'PRAGMA table_info({table})')}

    def read(table, date):
        available = columns(table)
        fields = [name if name in available else 'NULL' for name in ('artist', 'title', 'rating_key')]
        return conn.execute(f"SELECT {date}, {', '.join(fields)} FROM {table}").fetchall()

    sources = []
    if 'lastfm_scrobbles' in tables:
        sources.append(('lastfm', read('lastfm_scrobbles', 'timestamp')))
    if 'plex_play_events' in tables:
        sources.append(('plex', read('plex_play_events', 'timestamp')))
    if 'itunes_history' in tables:
        fields = columns('itunes_history')
        metadata = ', '.join('h.' + name if name in fields else 'NULL'
                             for name in ('artist', 'title', 'rating_key'))
        dated = "SELECT library_id, track_id, last_played AS played_at FROM itunes_history WHERE play_count > 0"
        if 'itunes_play_events' in tables:
            dated += ' UNION SELECT library_id, track_id, played_at FROM itunes_play_events'
        rows = conn.execute(f"""SELECT CAST(strftime('%s', e.played_at) AS INTEGER), {metadata}
            FROM ({dated}) e LEFT JOIN itunes_history h
            ON h.library_id=e.library_id AND h.track_id=e.track_id
            WHERE julianday(e.played_at) IS NOT NULL""").fetchall()
        sources.append(('itunes', rows))

    # Match only across sources. Keep repeated plays within each source intact.
    # Track keys and normalized artist/title are alternative matching identities.
    known = defaultdict(list)
    periods = {'year': defaultdict(int), 'month': defaultdict(int)}
    source_periods = {'year': defaultdict(lambda: defaultdict(int)),
                      'month': defaultdict(lambda: defaultdict(int))}
    contributions, duplicates = {}, 0
    for source, rows in sources:
        accepted = []
        contributions[source] = 0
        for timestamp, artist, title, key in rows:
            if timestamp is None:
                continue
            timestamp = int(timestamp)
            identities = []
            if key:
                identities.append(('key', str(key)))
            if artist and title:
                identities.append(('name', artist.strip().casefold(), title.strip().casefold()))
            overlap = False
            for identity in identities:
                dates = known[identity]
                pos = bisect_left(dates, timestamp - 60)
                if pos < len(dates) and dates[pos] <= timestamp + 60:
                    overlap = True
                    break
            if overlap:
                duplicates += 1
                continue
            try:
                played = datetime.fromtimestamp(timestamp)
            except (ValueError, OSError, OverflowError):
                continue
            for unit, pattern in [('year', '%Y'), ('month', '%Y-%m')]:
                period = played.strftime(pattern)
                periods[unit][period] += 1
                source_periods[unit][period][source] += 1
            contributions[source] += 1
            accepted.extend((identity, timestamp) for identity in identities)
        for identity, timestamp in accepted:
            known[identity].append(timestamp)
        for dates in known.values():
            dates.sort()
    return {**{unit: [{unit: period, 'plays': count,
                             **{source: source_periods[unit][period][source]
                                for source in ('lastfm', 'plex', 'itunes')}} for period, count in sorted(values.items())]
               for unit, values in periods.items()},
            'total': sum(contributions.values()), 'sources': contributions, 'duplicates': duplicates}
