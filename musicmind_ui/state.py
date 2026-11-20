"""Reflex state and data loading for MusicMind pages."""

import asyncio
import copy
import sqlite3

import reflex as rx
from musicmind.paths import PROJECT_ROOT
from musicmind_ui import jobs
from musicmind_ui.collection import ranked_rows, timeline_rows
from musicmind_ui.job_definitions import JOB_GROUPS

try:
    from config import DB_PATH, LASTFM_KEY
except ImportError:
    # Reflex compiles pages before the Docker entrypoint creates config.py.
    DB_PATH = str(PROJECT_ROOT / "musicmind.db")
    LASTFM_KEY = ""


def _legacy(method: str, path: str, payload: dict | None = None) -> dict:
    from web.app import app as flask_app

    with flask_app.test_client() as client:
        # Reflex wraps mutable state values in MutableProxy. Flask's JSON
        # encoder needs plain values, including for nested lists and dicts.
        response = client.open(path, method=method, json=copy.deepcopy(payload))
        try:
            data = response.get_json()
        except Exception:
            data = None
        if response.status_code >= 400:
            raise RuntimeError((data or {}).get("error", f"HTTP {response.status_code}"))
        return data if data is not None else {}


def _query_logs() -> list[dict]:
    with sqlite3.connect(DB_PATH, timeout=30) as conn:
        rows = conn.execute(
            "SELECT timestamp, prompt, result_count, duration_ms, error, cost_usd "
            "FROM query_log ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return [
        {"timestamp": r[0] or "", "prompt": r[1] or "", "count": r[2] or 0,
         "duration": r[3] or 0, "error": r[4] or "", "cost": r[5] or 0}
        for r in rows
    ]


def _guide() -> str:
    return (PROJECT_ROOT / "USER-MANUAL.md").read_text()


def _home_stats() -> dict[str, int]:
    totals = {"tracks": 0, "artists": 0, "plays": 0}
    conn = sqlite3.connect(DB_PATH, timeout=10)
    try:
        totals["tracks"] = conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]
        totals["artists"] = conn.execute(
            "SELECT COUNT(DISTINCT COALESCE(real_artist, artist)) FROM tracks "
            "WHERE artist IS NOT NULL AND artist != ''"
        ).fetchone()[0]
        totals["plays"] = conn.execute("SELECT COUNT(*) FROM lastfm_scrobbles").fetchone()[0]
    except sqlite3.Error:
        pass  # A fresh install may not have created the library tables yet.
    finally:
        conn.close()
    return totals


class UI(rx.State):
    itunes_importing: bool = False
    itunes_result: str = ""

    async def import_itunes(self, files: list[rx.UploadFile]):
        from musicmind.itunes import MAX_UPLOAD_BYTES, import_library

        self.itunes_importing = True
        self.itunes_result = "Importing iTunes library…"
        yield
        try:
            if len(files) != 1:
                raise ValueError("Select one library XML export.")
            data = await files[0].read(MAX_UPLOAD_BYTES + 1)
            result = await asyncio.to_thread(import_library, data, DB_PATH)
            self.itunes_result = (
                f"Imported {result['imported']} tracks; {result['matched']} stored tracks matched to Plex; "
                f"{result['skipped']} skipped. Reimporting does not add duplicate plays."
            )
            yield rx.clear_selected_files("itunes-library")
        except Exception as exc:
            self.itunes_result = f"Import failed: {exc}"
        finally:
            for file in files:
                await file.close()
            self.itunes_importing = False

    theme: str = "light"
    filters_open: bool = False
    filter_section: str = "Sound"
    genre_families_open: bool = False
    busy: bool = False
    message: str = ""
    prompt: str = ""
    playlist_name: str = ""
    has_searched: bool = False
    show_all_playlists: bool = False
    tracks: list[dict] = []
    tags: list[str] = []
    playlists: list[dict] = []
    home_stats: dict[str, int] = {"tracks": 0, "artists": 0, "plays": 0, "playlists": 0}
    home_stats_display: dict[str, str] = {"tracks": "0", "artists": "0", "plays": "0", "playlists": "0"}
    plex_machine_id: str = ""
    genres: list[dict] = []
    countries: list[dict] = []
    filters: dict[str, str] = {"limit": "30", "max_per_artist": "1", "order": "BPM flow"}
    unplayed: bool = False
    instrumental: bool = False
    buckets: list[str] = []
    based_on_query: str = ""
    suggestions: list[dict] = []
    selected_seed: dict = {}
    on_this_day: str = ""
    resync_artist: str = ""
    resync_album: str = ""
    resync_apply: bool = False
    synapse_limit: str = "10"
    missing: list[dict] = []
    stats: dict = {}
    stats_summary: dict[str, int] = {"total_tracks": 0, "total_artists": 0,
                                     "total_scrobbles": 0, "total_instrumental": 0}
    stats_display: dict[str, str] = {"total_tracks": "0", "total_artists": "0",
                                     "total_scrobbles": "0", "total_instrumental": "0"}
    stats_loading: bool = False
    stats_loaded: bool = False
    stats_error: str = ""
    stats_request: int = 0
    stats_pages: dict[str, int] = {"artist": 0, "genre": 0, "country": 0}
    stats_rankings: dict[str, list[dict]] = {"artist": [], "genre": [], "country": []}
    listening_rows: list[dict] = []
    era_rows: list[dict] = []
    gender_rows: list[dict] = []

    @rx.var
    def stats_visible(self) -> dict[str, list[dict]]:
        return {kind: rows[self.stats_pages[kind] * 10:(self.stats_pages[kind] + 1) * 10]
                for kind, rows in self.stats_rankings.items()}

    @rx.var
    def stats_ranges(self) -> dict[str, str]:
        return {kind: (f"{self.stats_pages[kind] * 10 + 1}–"
                       f"{min((self.stats_pages[kind] + 1) * 10, len(rows))} of {len(rows)} loaded"
                       if rows else "0 loaded") for kind, rows in self.stats_rankings.items()}

    def stats_turn_page(self, kind: str, direction: int):
        if kind not in self.stats_pages:
            return
        last = max(0, (len(self.stats_rankings[kind]) - 1) // 10)
        self.stats_pages[kind] = max(0, min(last, self.stats_pages[kind] + direction))

    artist_limit: str = "10"
    genre_limit: str = "10"
    country_limit: str = "10"
    top_artists: list[dict] = []
    top_genres: list[dict] = []
    genre_source: str = "tags"
    by_country: list[dict] = []
    by_era: list[dict] = []
    by_gender: list[dict] = []
    listening_by_year: list[dict] = []
    listening_by_month: list[dict] = []
    listening_granularity: str = "year"
    logs: list[dict] = []
    sql: str = "SELECT * FROM tracks LIMIT 20"
    query_columns: list[str] = []
    query_rows: list[list[str]] = []
    gaps: list[dict] = []
    gap_buckets: list[dict] = []
    selected_job: str = "fullsync"
    selected_job_label: str = "Full sync"
    job_log: str = ""
    job_running: bool = False
    job_dialog_open: bool = False
    fullsync_phase: str = "Waiting to start"
    fullsync_progress: int = 0
    fullsync_step: int = 0
    running_jobs: list[str] = []
    open_job_groups: list[str] = []
    synapse: dict = {}
    synapse_errors: list[dict] = []
    playlist_key: str = ""
    audit: dict = {}
    audit_tracks: list[dict[str, str]] = []
    update_info: dict = {}
    guide_text: str = ""

    def set_prompt(self, value: str):
        self.prompt = value

    def set_theme(self, value: str):
        if value in {"light", "parchment", "midnight", "ocean", "forest"}:
            self.theme = value

    def toggle_filters(self):
        self.filters_open = not self.filters_open

    def set_filter_section(self, value: str):
        if value in {"Sound", "Context", "Limits"}:
            self.filter_section = value

    def toggle_genre_families(self):
        self.genre_families_open = not self.genre_families_open

    def set_playlist_name(self, value: str):
        self.playlist_name = value

    def set_based_on_query(self, value: str):
        self.based_on_query = value

    def set_on_this_day(self, value: str):
        self.on_this_day = value

    def set_sql(self, value: str):
        self.sql = value

    def set_playlist_key(self, value: str):
        self.playlist_key = value

    def set_resync_artist(self, value: str):
        self.resync_artist = value

    def set_resync_album(self, value: str):
        self.resync_album = value

    def set_resync_apply(self, value: bool):
        self.resync_apply = value

    def set_synapse_limit(self, value: str):
        self.synapse_limit = value

    def set_unplayed(self, value: bool):
        self.unplayed = value

    def set_instrumental(self, value: bool):
        self.instrumental = value

    @rx.var
    def genre_names(self) -> list[str]:
        return [item.get("tag", "") for item in self.genres]

    @rx.var
    def country_names(self) -> list[str]:
        return [item.get("country", "") for item in self.countries]

    @rx.var
    def visible_playlists(self) -> list[dict]:
        return self.playlists if self.show_all_playlists else self.playlists[:6]

    def toggle_all_playlists(self):
        self.show_all_playlists = not self.show_all_playlists

    def set_filter(self, key: str, value: str):
        self.filters = {**self.filters, key: value}

    def clear_message(self):
        self.message = ""

    def toggle_bucket(self, bucket: str, enabled: bool):
        self.buckets = ([*self.buckets, bucket] if enabled else [b for b in self.buckets if b != bucket])

    async def home_load(self):
        self.genre_families_open = False
        self.show_all_playlists = False
        try:
            genres, countries, playlists, home_stats = await asyncio.gather(
                asyncio.to_thread(_legacy, "GET", "/genres"),
                asyncio.to_thread(_legacy, "GET", "/countries"),
                asyncio.to_thread(_legacy, "GET", "/playlists"),
                asyncio.to_thread(_home_stats),
            )
            self.genres = sorted(genres, key=lambda x: x.get("tag", ""))
            self.countries = sorted(countries, key=lambda x: x.get("country", ""))
            self.plex_machine_id = playlists.get("machineId", "")
            self.playlists = [
                {**item, "url": f"https://app.plex.tv/desktop/#!/server/{self.plex_machine_id}/playlist?key=%2Fplaylists%2F{item['key']}"}
                for item in playlists.get("playlists", [])
            ]
            self.home_stats = {**home_stats, "playlists": len(self.playlists)}
            self.home_stats_display = {key: "0" for key in self.home_stats}
            yield
            for step in range(1, 25):
                progress = 1 - (1 - step / 24) ** 3
                self.home_stats_display = {
                    key: f"{round(value * progress):,}"
                    for key, value in self.home_stats.items()
                }
                yield
                await asyncio.sleep(0.025)
        except Exception as exc:
            self.message = str(exc)

    async def preview(self):
        self.busy = True
        self.message = "Finding tracks…"
        yield
        try:
            payload = {**self.filters, "prompt": self.prompt, "buckets": self.buckets,
                       "unplayed": self.unplayed, "instrumental": self.instrumental}
            result = await asyncio.to_thread(_legacy, "POST", "/preview", payload)
            self.tracks = result.get("tracks", [])
            self.has_searched = True
            self.tags = result.get("tags", [])
            self.missing = []
            self.playlist_name = self.prompt or "My Playlist"
            self.message = result.get("warning") or f"{len(self.tracks)} tracks matched"
        except Exception as exc:
            self.message = str(exc)
        finally:
            self.busy = False

    async def search_seed(self):
        if len(self.based_on_query.strip()) < 2:
            self.suggestions = []
            return
        try:
            from urllib.parse import quote
            result = await asyncio.to_thread(_legacy, "GET", f"/based-on-search?q={quote(self.based_on_query)}")
            self.suggestions = result.get("results", [])
        except Exception as exc:
            self.message = str(exc)

    async def select_seed(self, seed: dict):
        self.selected_seed = seed
        self.based_on_query = seed.get("label", "")
        self.suggestions = []
        self.busy = True
        yield
        try:
            payload = {**seed, "limit": self.filters.get("limit", "30"),
                       "max_per_artist": self.filters.get("max_per_artist", "1"),
                       "order": self.filters.get("order", "BPM flow")}
            result = await asyncio.to_thread(_legacy, "POST", "/based-on", payload)
            self.tracks = result.get("tracks", [])
            self.has_searched = True
            self.tags = [f"Based on: {seed.get('label', '')}"]
            self.message = f"{len(self.tracks)} similar tracks"
            self.playlist_name = f"Based on {seed.get('label', '')}"
        except Exception as exc:
            self.message = str(exc)
        finally:
            self.busy = False

    async def find_on_this_day(self):
        self.busy = True
        yield
        try:
            result = await asyncio.to_thread(_legacy, "POST", "/onthisday", {
                "date": self.on_this_day, "limit": self.filters.get("limit", "30"),
                "max_per_artist": self.filters.get("max_per_artist", "1"),
                "order": self.filters.get("order", "BPM flow")})
            self.tracks = result.get("tracks", [])
            self.has_searched = True
            self.missing = result.get("missing", [])
            self.tags = [result.get("search_term", "")]
            self.message = f"{len(self.tracks)} tracks matched"
            self.playlist_name = f"On this day {self.on_this_day}"
        except Exception as exc:
            self.message = str(exc)
        finally:
            self.busy = False

    async def create_playlist(self):
        self.busy = True
        yield
        try:
            result = await asyncio.to_thread(_legacy, "POST", "/create", {
                "name": self.playlist_name, "rating_keys": [t["rating_key"] for t in self.tracks],
                "prompt": self.prompt})
            self.message = f"Created {result.get('name')} with {result.get('count')} tracks in Plex"
            async for _ in self.home_load():
                yield
        except Exception as exc:
            self.message = str(exc)
        finally:
            self.busy = False

    async def stats_load(self):
        self.stats_request += 1
        request = self.stats_request
        self.stats_loading = True
        self.stats_error = ""
        yield
        try:
            path = (f"/stats/data?artist_limit={self.artist_limit}"
                    f"&genre_limit={self.genre_limit}&country_limit={self.country_limit}")
            data = await asyncio.to_thread(_legacy, "GET", path)
            if request != self.stats_request:
                return
            summary = data["stats"]
            rankings = {
                "artist": ranked_rows(data["top_artists"], "artist", "plays"),
                "genre": ranked_rows(data["top_genres"], "tag", "cnt"),
                "country": ranked_rows(data["by_country"], "country", "cnt"),
            }
            granularity = data.get("listening_granularity", "year")
            listening = timeline_rows(data[f"listening_by_{granularity}"], granularity)
            self.stats = data
            self.stats_summary = summary
            self.stats_display = {key: "0" for key in summary}
            self.stats_rankings = rankings
            for kind, rows in rankings.items():
                self.stats_pages[kind] = min(self.stats_pages[kind], max(0, (len(rows) - 1) // 10))
            self.genre_source = data.get("genre_source", "tags")
            self.by_era = data["by_era"]
            self.era_rows = ranked_rows(data["by_era"], "era", "cnt")
            self.gender_rows = ranked_rows(data["by_gender"], "gender", "cnt")
            self.listening_rows = listening
            self.listening_granularity = granularity
            self.stats_loaded = True
            self.stats_loading = False
            yield
            for step in range(1, 25):
                if request != self.stats_request:
                    return
                progress = 1 - (1 - step / 24) ** 3
                self.stats_display = {
                    key: f"{round(value * progress):,}"
                    for key, value in summary.items()
                }
                yield
                await asyncio.sleep(0.025)
        except Exception as exc:
            if request == self.stats_request:
                self.stats_error = f"Could not load collection data: {exc}"
        finally:
            if request == self.stats_request:
                self.stats_loading = False
                yield

    async def set_stats_limit(self, kind: str, value: str):
        if kind not in {"artist", "genre", "country"} or value not in {"10", "25", "50", "100"}:
            return
        setattr(self, f"{kind}_limit", value)
        self.stats_pages[kind] = 0
        async for event in self.stats_load():
            yield event

    async def logs_load(self):
        try:
            self.logs = await asyncio.to_thread(_query_logs)
        except Exception as exc:
            self.message = str(exc)

    async def run_query(self):
        self.busy = True
        yield
        try:
            result = await asyncio.to_thread(_legacy, "POST", "/query", {"sql": self.sql})
            self.query_columns = result.get("columns", [])
            self.query_rows = [[str(v) for v in row] for row in result.get("rows", [])]
            self.message = f"{len(self.query_rows)} rows"
        except Exception as exc:
            self.message = str(exc)
        finally:
            self.busy = False

    async def gaps_load(self):
        def load():
            with sqlite3.connect(DB_PATH, timeout=30) as conn:
                rows = conn.execute("SELECT category, artist, scrobbles FROM artist_gaps ORDER BY scrobbles DESC").fetchall()
            return [{"category": r[0], "artist": r[1], "scrobbles": r[2]} for r in rows]
        try:
            self.gaps = await asyncio.to_thread(load)
            categories = [("worth_acquiring", "Worth acquiring", "Frequently played artists to add to your collection.", "music"),
                          ("classical", "Classical", "Composers and performers missing from your library.", "piano"),
                          ("ambient_meditation", "Ambient / Meditation", "Atmospheric and meditative listening to revisit.", "waves"),
                          ("unknown", "Unknown", "Artists whose category has not been identified.", "circle-help")]
            self.gap_buckets = [
                {"key": key, "label": label, "description": description,
                 "artists": [dict(row) for row in self.gaps if (row["category"] or "unknown") == key],
                 "count": sum(1 for row in self.gaps if (row["category"] or "unknown") == key)}
                for key, label, description, icon in categories
            ]
        except Exception as exc:
            self.message = str(exc)

    async def job_load(self):
        try:
            result = await asyncio.to_thread(jobs.status, self.selected_job)
            self.job_log = result["log"]
            self.job_running = result["running"]
            if self.selected_job == "fullsync":
                self.fullsync_phase = result.get("phase", "Waiting to start")
                self.fullsync_progress = result.get("progress", 0)
                self.fullsync_step = result.get("step", 0)
            current = [name for name in self.running_jobs if name != self.selected_job]
            self.running_jobs = current + ([self.selected_job] if self.job_running else [])
        except Exception as exc:
            self.message = str(exc)

    async def jobs_load(self):
        names = ["fullsync"]
        names.extend(name for group, _, entries in JOB_GROUPS for name, _, _ in entries)
        names.extend(["synapse_full", "synapse_limited"])
        names.extend(jobs.GROUP_COMMANDS)
        results = await asyncio.gather(*[
            asyncio.to_thread(jobs.status, name) for name in names
        ], return_exceptions=True)
        fullsync_result = results[0]
        if isinstance(fullsync_result, dict):
            self.fullsync_phase = fullsync_result.get("phase", "Waiting to start")
            self.fullsync_progress = fullsync_result.get("progress", 0)
            self.fullsync_step = fullsync_result.get("step", 0)
        self.running_jobs = [name for name, result in zip(names, results)
                             if isinstance(result, dict) and result["running"]]
        try:
            self.synapse = await asyncio.to_thread(_legacy, "GET", "/synapse-status")
        except Exception as exc:
            self.message = str(exc)
        await self.job_load()

    async def admin_load(self):
        self.job_dialog_open = False
        await self.jobs_load()
        return UI.poll_jobs

    @rx.event(background=True)
    async def poll_jobs(self):
        while True:
            await asyncio.sleep(1.5)
            async with self:
                await self.jobs_load()
                active = bool(self.running_jobs)
            if not active:
                break

    async def watch_job(self):
        # Queue polling as a background task, releasing the event queue so
        # Status, Close, and other controls respond during long jobs.
        yield UI.poll_jobs

    async def select_job(self, name: str):
        self.selected_job = name
        self.selected_job_label = _job_label(name)
        self.job_dialog_open = True
        yield
        await self.job_load()
        async for _ in self.watch_job():
            yield

    def set_job_dialog_open(self, is_open: bool):
        self.job_dialog_open = is_open

    def toggle_job_group(self, group: str):
        self.open_job_groups = ([name for name in self.open_job_groups if name != group]
                                if group in self.open_job_groups
                                else [*self.open_job_groups, group])

    async def start_job(self, name: str):
        self.selected_job = name
        self.selected_job_label = _job_label(name)
        self.job_dialog_open = True
        yield
        try:
            await asyncio.to_thread(jobs.start, name)
            self.message = f"{name} started"
            await self.job_load()
            async for _ in self.watch_job():
                yield
        except Exception as exc:
            self.message = str(exc)

    async def stop_job(self, name: str):
        try:
            await asyncio.to_thread(jobs.stop, name)
            self.message = f"{name} stopped"
            await self.jobs_load()
        except Exception as exc:
            self.message = str(exc)

    async def start_resync(self):
        self.selected_job = "resync"
        self.selected_job_label = _job_label("resync")
        self.job_dialog_open = True
        yield
        try:
            args = [self.resync_artist, self.resync_album]
            if self.resync_apply:
                args.append("--run")
            await asyncio.to_thread(jobs.start, "resync", args)
            self.message = "Resync started"
            await self.job_load()
            async for _ in self.watch_job():
                yield
        except Exception as exc:
            self.message = str(exc)

    async def start_synapse_limited(self):
        self.selected_job = "synapse_limited"
        self.selected_job_label = _job_label("synapse_limited")
        self.job_dialog_open = True
        yield
        try:
            await asyncio.to_thread(jobs.start, "synapse_limited", [self.synapse_limit])
            self.message = "Limited Synapse run started"
            await self.job_load()
            async for _ in self.watch_job():
                yield
        except Exception as exc:
            self.message = str(exc)

    async def scan_plex(self):
        try:
            result = await asyncio.to_thread(_legacy, "GET", "/scan")
            self.message = result.get("message", "Scan requested")
        except Exception as exc:
            self.message = str(exc)

    async def synapse_load(self):
        try:
            self.synapse = await asyncio.to_thread(_legacy, "GET", "/synapse-status")
        except Exception as exc:
            self.message = str(exc)

    async def synapse_errors_load(self):
        try:
            self.synapse_errors = await asyncio.to_thread(_legacy, "GET", "/synapse-errors")
        except Exception as exc:
            self.message = str(exc)

    async def playlists_load(self):
        try:
            result = await asyncio.to_thread(_legacy, "GET", "/playlists")
            self.plex_machine_id = result.get("machineId", "")
            self.playlists = [
                {**item, "url": f"https://app.plex.tv/desktop/#!/server/{self.plex_machine_id}/playlist?key=%2Fplaylists%2F{item['key']}"}
                for item in result.get("playlists", [])
            ]
        except Exception as exc:
            self.message = str(exc)

    async def audit_load(self):
        key = self.playlist_key.strip()
        if not key.isdigit():
            self.message = "Select a playlist or enter its numeric Plex playlist ID."
            return
        try:
            self.audit = {}
            self.audit_tracks = []
            self.audit = await asyncio.to_thread(_legacy, "GET", f"/playlist-audit-data/{key}")
            self.audit_tracks = [
                {"number": str(index), "title": track.get("title") or "Untitled",
                 "artist": track.get("artist") or "Unknown artist",
                 "bpm": str(track["bpm"]) if track.get("bpm") is not None else "—",
                 "danceability": str(track["danceability"]) if track.get("danceability") is not None else "—",
                 "voice": f'{track["p_voice"]:.0%}' if track.get("p_voice") is not None else "—",
                 "verdict": track.get("vi_verdict") or "Not analyzed"}
                for index, track in enumerate(self.audit.get("tracks", []), 1)
            ]
        except Exception as exc:
            self.message = str(exc)

    async def select_playlist(self, key: str):
        self.playlist_key = key
        await self.audit_load()

    async def update_load(self):
        try:
            self.update_info = await asyncio.to_thread(_legacy, "GET", "/check-update")
        except Exception as exc:
            self.message = str(exc)

    async def guide_load(self):
        self.guide_text = await asyncio.to_thread(_guide)

    async def run_assertion(self, key: str):
        try:
            self.audit = await asyncio.to_thread(_legacy, "GET", f"/run/assertion/{key}")
        except Exception as exc:
            self.message = str(exc)


