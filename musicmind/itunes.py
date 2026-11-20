"""Import aggregate listening history from an iTunes/Music XML library export."""

from datetime import datetime, timezone
import plistlib
import sqlite3

MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def init_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS itunes_history (
        library_id TEXT NOT NULL, track_id TEXT NOT NULL,
        artist TEXT NOT NULL, title TEXT NOT NULL, album TEXT NOT NULL,
        play_count INTEGER NOT NULL, last_played TEXT,
        rating_key TEXT, PRIMARY KEY (library_id, track_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS itunes_play_events (
        library_id TEXT NOT NULL, track_id TEXT NOT NULL, played_at TEXT NOT NULL,
        PRIMARY KEY (library_id, track_id, played_at)
    )""")
    # Keep observed dates, without distributing aggregate counts over invented dates.
    conn.execute("""INSERT OR IGNORE INTO itunes_play_events
        SELECT library_id, track_id, last_played FROM itunes_history
        WHERE play_count > 0 AND julianday(last_played) IS NOT NULL""")
    if 'user_rating' not in {row[1] for row in conn.execute('PRAGMA table_info(itunes_history)')}:
        conn.execute('ALTER TABLE itunes_history ADD COLUMN user_rating REAL')


def apply_history(conn):
    """Rematch stored records, including after new Plex tracks are ingested."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='itunes_history'").fetchone():
        return
    init_table(conn)
    index = {}
    for key, artist, title, album, real_artist in conn.execute(
        "SELECT rating_key, artist, title, album, real_artist FROM tracks"
    ):
        for name in {artist, real_artist} - {None, ""}:
            index.setdefault((name.strip().casefold(), (title or '').strip().casefold()), {})[key] = (album or '').strip().casefold()
    for library, track, artist, title, album in conn.execute(
        "SELECT library_id, track_id, artist, title, album FROM itunes_history"
    ).fetchall():
        candidates = index.get((artist.strip().casefold(), title.strip().casefold()), {})
        if album:
            candidates = {k: a for k, a in candidates.items() if a == album.strip().casefold()}
        key = next(iter(candidates)) if len(candidates) == 1 else None
        conn.execute("UPDATE itunes_history SET rating_key=? WHERE library_id=? AND track_id=?", (key, library, track))
    conn.execute("""UPDATE tracks SET
        play_count=MAX(COALESCE(play_count,0), (SELECT MAX(play_count) FROM itunes_history h WHERE h.rating_key=tracks.rating_key)),
        last_played=CASE WHEN last_played IS NULL OR julianday(last_played) < julianday((SELECT MAX(last_played) FROM itunes_history h WHERE h.rating_key=tracks.rating_key))
            THEN COALESCE((SELECT MAX(last_played) FROM itunes_history h WHERE h.rating_key=tracks.rating_key), last_played) ELSE last_played END
        WHERE rating_key IN (SELECT rating_key FROM itunes_history WHERE rating_key IS NOT NULL)""")
    conn.execute("""UPDATE tracks SET user_rating=(
        SELECT MAX(user_rating) FROM itunes_history h WHERE h.rating_key=tracks.rating_key
    ) WHERE COALESCE(user_rating,0)=0 AND rating_key IN (
        SELECT rating_key FROM itunes_history WHERE user_rating > 0
    )""")


def import_library(data: bytes, db_path: str) -> dict[str, int]:
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("Library export exceeds the 50 MiB limit.")
    try:
        library = plistlib.loads(data)
    except Exception as exc:
        raise ValueError("Upload an iTunes or Apple Music library XML export, not an .itl file.") from exc
    if not isinstance(library, dict) or not isinstance(library.get('Tracks'), dict) or not library.get('Library Persistent ID'):
        raise ValueError("The export must contain Tracks and a Library Persistent ID. Export the entire library as XML.")
    library_id = library['Library Persistent ID']
    if not isinstance(library_id, str):
        raise ValueError("Invalid library identifier.")
    records = []
    skipped = 0
    for track in library['Tracks'].values():
        if not isinstance(track, dict):
            skipped += 1
            continue
        artist, title = track.get('Artist'), track.get('Name')
        track_id = track.get('Persistent ID')
        count = track.get('Play Count', 0)
        album = track.get('Album', '')
        played = track.get('Play Date UTC')
        if (not all(isinstance(v, str) and v.strip() for v in (artist, title, track_id))
                or not isinstance(album, str) or type(count) is not int or not 0 <= count <= 2147483647
                or (played is not None and not isinstance(played, datetime))):
            skipped += 1
            continue
        if played is not None:
            played = played.replace(tzinfo=timezone.utc) if played.tzinfo is None else played.astimezone(timezone.utc)
        rating = track.get('Rating')
        user_rating = (
            rating / 10 if type(rating) is int and 0 < rating <= 100
            and not track.get('Rating Computed', False) else None
        )
        records.append((library_id, track_id, artist, title, album, count,
                        played.isoformat() if played else None, user_rating))
    with sqlite3.connect(db_path, timeout=30) as conn:
        init_table(conn)
        conn.executemany("""INSERT INTO itunes_history (library_id,track_id,artist,title,album,play_count,last_played,user_rating)
            VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(library_id,track_id) DO UPDATE SET
            artist=excluded.artist,title=excluded.title,album=excluded.album,
            play_count=MAX(itunes_history.play_count,excluded.play_count),
            last_played=MAX(COALESCE(itunes_history.last_played,''),COALESCE(excluded.last_played,'')),
            user_rating=excluded.user_rating""", records)
        conn.executemany("""INSERT OR IGNORE INTO itunes_play_events
            (library_id, track_id, played_at) VALUES (?, ?, ?)""",
            [(library, track, played) for library, track, _, _, _, count, played, _ in records
             if count > 0 and played is not None])
        apply_history(conn)
        matched = conn.execute("SELECT COUNT(*) FROM itunes_history WHERE library_id=? AND rating_key IS NOT NULL", (library_id,)).fetchone()[0]
    return {'imported': len(records), 'matched': matched, 'skipped': skipped}


def sync_ratings_to_plex(db_path, plex):
    """Pull explicit Plex ratings; fill only unrated Plex tracks from MusicMind."""
    result = {'synced': 0, 'unchanged': 0, 'refreshed': 0, 'failed': 0}
    with sqlite3.connect(db_path, timeout=30) as conn:
        rows = conn.execute('SELECT rating_key, user_rating FROM tracks').fetchall()
    updates = []
    for key, rating in rows:
        try:
            track = plex.fetchItem(int(key))
            plex_rating = track.userRating
            if plex_rating is not None and 0 < plex_rating <= 10:
                if rating != plex_rating:
                    updates.append((plex_rating, key))
                    result['refreshed'] += 1
                else:
                    result['unchanged'] += 1
            elif rating is not None and 0 < rating <= 10:
                track.rate(rating)
                result['synced'] += 1
            else:
                result['unchanged'] += 1
        except Exception:
            result['failed'] += 1
    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.executemany('UPDATE tracks SET user_rating=? WHERE rating_key=?', updates)
    return result


def listening_history(conn: sqlite3.Connection) -> dict:
    """Known dated plays, kept separate from potentially overlapping scrobbles."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    queries = []
    if 'itunes_history' in tables:
        queries.append("SELECT library_id, track_id, last_played AS played_at FROM itunes_history WHERE play_count > 0")
    if 'itunes_play_events' in tables:
        queries.append("SELECT library_id, track_id, played_at FROM itunes_play_events")
    if not queries:
        return {'year': [], 'month': [], 'total': 0}
    events = ' UNION '.join(queries)
    result = {}
    for name, pattern in [('year', '%Y'), ('month', '%Y-%m')]:
        result[name] = [{name: period, 'plays': count} for period, count in conn.execute(
            f"SELECT strftime(?, played_at, 'localtime') AS period, COUNT(*) FROM ({events}) "
            "WHERE julianday(played_at) IS NOT NULL GROUP BY period ORDER BY period", (pattern,))]
    result['total'] = sum(row['plays'] for row in result['year'])
    return result
