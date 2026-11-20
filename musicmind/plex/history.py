"""Import retained, dated Plex music plays for the collection timeline."""
import argparse
from datetime import datetime
import sqlite3


def sync_history(plex, db_path: str, library_name: str, account_id: int = 1) -> dict:
    library = plex.library.section(library_name)
    server_id = plex.machineIdentifier
    # Fetch before opening a write transaction; authentication failures must not
    # leave an incomplete import marked as successful.
    history = plex.history(librarySectionID=library.key, accountID=account_id)
    rows = []
    for item in history:
        if getattr(item, 'type', None) != 'track':
            continue
        played = getattr(item, 'viewedAt', None)
        history_key = getattr(item, 'historyKey', None)
        if not isinstance(played, datetime) or not history_key:
            continue
        rows.append((server_id, account_id, str(history_key), int(played.timestamp()),
                     str(item.ratingKey) if getattr(item, 'ratingKey', None) else None,
                     getattr(item, 'grandparentTitle', None), getattr(item, 'title', None)))
    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS plex_play_events (
            server_id TEXT NOT NULL, account_id INTEGER NOT NULL, history_key TEXT NOT NULL,
            timestamp INTEGER NOT NULL, rating_key TEXT, artist TEXT, title TEXT,
            PRIMARY KEY(server_id, account_id, history_key))''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_plex_play_timestamp ON plex_play_events(timestamp)')
        before = conn.total_changes
        conn.executemany('''INSERT OR IGNORE INTO plex_play_events
            (server_id,account_id,history_key,timestamp,rating_key,artist,title)
            VALUES (?,?,?,?,?,?,?)''', rows)
        added = conn.total_changes - before
    dates = [row[3] for row in rows]
    return {'available': len(rows), 'added': added,
            'earliest': datetime.fromtimestamp(min(dates)).isoformat() if dates else None,
            'latest': datetime.fromtimestamp(max(dates)).isoformat() if dates else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--account-id', type=int, default=1,
                        help='Plex local account ID (default: 1, server owner)')
    args = parser.parse_args()
    from config import DB_PATH, MUSIC_LIB, PLEX_TOKEN, PLEX_URL
    from plexapi.server import PlexServer
    try:
        result = sync_history(PlexServer(PLEX_URL, PLEX_TOKEN, timeout=30), DB_PATH, MUSIC_LIB, args.account_id)
    except Exception as exc:
        # Avoid echoing request URLs, which can contain Plex authentication data.
        print(f'Plex history sync failed ({type(exc).__name__}). Check server access and credentials.', flush=True)
        raise SystemExit(1) from None
    print(f"Plex history: {result['available']:,} dated music plays; {result['added']:,} added.", flush=True)
    if result['earliest']:
        print(f"Available range: {result['earliest']} to {result['latest']}", flush=True)
    else:
        print('No retained music playback history was returned for this account.', flush=True)


if __name__ == '__main__':
    main()
