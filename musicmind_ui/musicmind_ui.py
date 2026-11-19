"""Reflex pages for MusicMind.

The existing Flask request handlers remain as a compatibility API while the
interface is migrated. All calls into that synchronous API run in threads.
"""

import asyncio
import copy
from random import Random
import sqlite3

import reflex as rx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from musicmind.paths import PROJECT_ROOT

try:
    from config import DB_PATH, LASTFM_KEY
except ImportError:
    # Reflex compiles pages while Docker is building, before the entrypoint
    # creates config.py from environment variables.
    DB_PATH = str(PROJECT_ROOT / "musicmind.db")
    LASTFM_KEY = ""
from musicmind_ui import jobs


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
        try:
            path = (f"/stats/data?artist_limit={self.artist_limit}"
                    f"&genre_limit={self.genre_limit}&country_limit={self.country_limit}")
            self.stats = await asyncio.to_thread(_legacy, "GET", path)
            self.stats_summary = self.stats.get("stats", self.stats_summary)
            self.stats_display = {key: "0" for key in self.stats_summary}
            self.top_artists = self.stats.get("top_artists", [])
            self.top_genres = self.stats.get("top_genres", [])
            self.genre_source = self.stats.get("genre_source", "tags")
            self.by_country = self.stats.get("by_country", [])
            self.by_era = self.stats.get("by_era", [])
            self.by_gender = self.stats.get("by_gender", [])
            self.listening_by_year = self.stats.get("listening_by_year", [])
            self.listening_by_month = self.stats.get("listening_by_month", [])
            self.listening_granularity = self.stats.get("listening_granularity", "year")
            yield
            for step in range(1, 25):
                progress = 1 - (1 - step / 24) ** 3
                self.stats_display = {
                    key: f"{round(value * progress):,}"
                    for key, value in self.stats_summary.items()
                }
                yield
                await asyncio.sleep(0.025)
        except Exception as exc:
            self.message = str(exc)
            yield

    async def set_stats_limit(self, kind: str, value: str):
        if value not in {"10", "25", "50", "100"}:
            return
        setattr(self, f"{kind}_limit", value)
        async for _ in self.stats_load():
            yield

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


def nav():
    links = [("Playlists", "/"), ("Collection", "/stats"), ("Gaps", "/gaps")]
    admin_links = [("settings", "Overview", "/admin"),
                   ("database", "DB Console", "/db"),
                   ("search", "Playlist Audit", "/playlist-audit"),
                   ("flask-conical", "Tests", "/tests"),
                   ("brain", "Synapse", "/admin#synapse"),
                   ("logs", "Logs", "/logs"),
                   ("book-open", "Guide", "/guide"),
                   ("refresh-cw", "Update", "/update")]
    return rx.box(
        rx.link("MUSICMIND / PLEX", href="/", class_name="nav-brand"),
        rx.hstack(
            *[rx.link(label, href=path, class_name="nav-link") for label, path in links
              if LASTFM_KEY or path != "/gaps"],
            rx.menu.root(
                rx.menu.trigger(rx.button(rx.icon("settings", size=16), "Admin", rx.icon("chevron-down", size=14),
                                          variant="ghost", class_name="nav-admin-trigger")),
                rx.menu.content(
                    rx.text("WORKSPACE", class_name="admin-menu-label"),
                    *[rx.menu.item(rx.icon(icon, size=16), label, on_select=rx.redirect(path))
                      for icon, label, path in admin_links[:5]],
                    rx.menu.separator(),
                    rx.text("SUPPORT & ACTIVITY", class_name="admin-menu-label"),
                    *[rx.menu.item(rx.icon(icon, size=16), label, on_select=rx.redirect(path))
                      for icon, label, path in admin_links[5:]],
                    class_name="nav-admin-menu", align="end", side_offset=8)),
            class_name="nav-links", wrap="wrap"),
        rx.el.details(
            rx.el.summary(rx.icon("palette", size=17), rx.text("Appearance"),
                          rx.icon("chevron-down", size=14)),
            rx.box(rx.text("Make it yours", class_name="admin-palette-title"),
                   theme_selector(), class_name="admin-palette-content"),
            class_name="admin-palette nav-appearance"),
        class_name="site-nav",
    )


def theme_selector():
    return rx.box(
        *[rx.button(
            rx.box(rx.box(), rx.box(), rx.box(), class_name=f"palette-preview preview-{name}"),
            rx.hstack(rx.text(label),
                      rx.cond(UI.theme == name, rx.icon("check", size=15), rx.fragment()),
                      justify="between", width="100%"),
            on_click=UI.set_theme(name), aria_label=f"{label} theme",
            aria_pressed=UI.theme == name,
            class_name=rx.cond(UI.theme == name, "palette-option is-selected", "palette-option"))
          for name, label in [("light", "Light"), ("parchment", "Parchment"),
                              ("midnight", "Midnight"), ("ocean", "Ocean"),
                              ("forest", "Forest")]],
        class_name="palette-options",
    )


def shell(title: str, subtitle: str, *children, show_intro: bool = True):
    return rx.box(
        nav(),
        rx.cond(UI.message != "", rx.callout(UI.message, icon="info", class_name="notice")),
        *children,
        rx.text("MusicMind for Plex", class_name="footer"),
        class_name=rx.match(UI.theme,
            ("midnight", "app-shell theme-midnight"),
            ("parchment", "app-shell theme-parchment"),
            ("ocean", "app-shell theme-ocean"),
            ("forest", "app-shell theme-forest"),
            "app-shell"),
    )


def panel(title: str, *children, class_name: str = "panel", icon: str | None = None):
    heading = rx.heading(title, size="4")
    if icon:
        heading = rx.hstack(rx.icon(icon, size=24), heading, class_name="panel-icon-heading")
    return rx.box(heading, *children, class_name=class_name)


def filter_input(label: str, key: str, placeholder: str = ""):
    return rx.box(rx.text(label, class_name="field-label"),
                  rx.input(value=UI.filters.get(key, ""), placeholder=placeholder,
                           on_change=lambda value: UI.set_filter(key, value)), class_name="field")


def filter_select(label: str, key: str, options):
    return rx.box(rx.text(label, class_name="field-label"),
                  rx.select(options, value=UI.filters.get(key, ""),
                            on_change=lambda value: UI.set_filter(key, value),
                            placeholder="Any"), class_name="field")


BUCKETS = ["New Wave / Post-Punk / Synth", "Psych / Art Rock / Experimental",
           "Classic / Garage / Alt / Punk Rock", "Soul / Funk / R&B", "Jazz",
           "World / Reggae / Latin / Afro", "Hip-Hop / Rap", "Pop",
           "Classical / Orchestral / Cinematic",
           "Folk / Singer-Songwriter / Acoustic / Blues",
           "Country / Americana / Bluegrass",
           "Electronic / House / Techno / Downtempo", "Gospel",
           "Chant / Choral / Sacred"]


def track_row(track: dict):
    return rx.hstack(rx.box(rx.text(track["artist"], class_name="track-artist"),
                             rx.text(track["title"], class_name="track-title")),
                     rx.hstack(rx.cond(track.get("bpm") != None,
                                       rx.text(track.get("bpm").to_string(), " BPM", class_name="track-bpm"),
                                       rx.fragment()),
                               rx.text(track.get("year", ""), class_name="track-meta"),
                               class_name="track-facts"),
                     class_name="track-row", justify="between")


def home_art():
    return rx.box(
        rx.text("SIDE A  /  OPEN SESSION", class_name="home-art-kicker"),
        rx.heading("Follow the\nfeeling.", class_name="home-art-title"),
        rx.text("A good playlist starts with a little curiosity.", class_name="home-art-caption"),
        rx.box(rx.box(class_name="sound-wave wave-a"),
               rx.box(class_name="sound-wave wave-b"),
               rx.box(class_name="sound-wave wave-c"),
               rx.box(class_name="sound-wave wave-d"),
               rx.box(class_name="sound-wave wave-e"),
               rx.box(class_name="sound-wave wave-f"),
               rx.box(class_name="home-art-record"),
               rx.box(class_name="home-art-label"),
               class_name="home-art-visual", aria_hidden="true"),
        class_name="home-art-tile",
    )


def home_visual_gallery():
    return rx.box(
        rx.box(rx.box(class_name="gallery-disc"), rx.box(class_name="gallery-label"),
               rx.text("A / 01", class_name="gallery-mark"), class_name="gallery-art gallery-vinyl"),
        rx.box(rx.box(class_name="gallery-sun"), rx.box(class_name="gallery-horizon"),
               rx.text("GOLDEN HOUR", class_name="gallery-mark"), class_name="gallery-art gallery-sunset"),
        rx.box(rx.box(class_name="gallery-wave wave-one"), rx.box(class_name="gallery-wave wave-two"),
               rx.box(class_name="gallery-wave wave-three"),
               rx.text("STEREO / 02", class_name="gallery-mark"), class_name="gallery-art gallery-wave-card"),
        class_name="home-visual-gallery", aria_hidden="true",
    )


def home_stat(label: str, key: str, detail: str, accent: str):
    return rx.box(rx.text(label, class_name="home-stat-label"),
                  rx.text(UI.home_stats_display.get(key, "0"), class_name="home-stat-value"),
                  rx.text(detail, class_name="home-stat-detail"),
                  class_name=f"home-stat {accent}")


def home():
    return shell("", "",
        rx.box(
            home_visual_gallery(),
            panel("What are you in the mood for?",
                rx.input(value=UI.prompt, on_change=UI.set_prompt,
                         placeholder="sunny day driving with the windows down…", size="3", width="100%"),
                rx.text("Describe a mood, artist, title, or year.", class_name="home-helper"),
                rx.button("Find tracks", on_click=UI.preview, disabled=UI.busy),
                rx.box(
                    rx.hstack(rx.button("Tune the search", rx.cond(UI.filters_open,
                                                                    rx.icon("chevron-up", size=16),
                                                                    rx.icon("chevron-down", size=16)),
                                        on_click=UI.toggle_filters, variant="outline",
                                        aria_expanded=UI.filters_open, class_name="tune-search-button"),
                              justify="center", align="center", class_name="inline-filter-toggle"),
                    rx.cond(UI.filters_open,
                        rx.box(
                            rx.box(rx.box(rx.text("PLAYLIST ORDER", class_name="filter-group-kicker"),
                                          rx.select(["BPM flow", "BPM ascending", "BPM descending", "Best match"],
                                                    value=UI.filters.get("order", "BPM flow"),
                                                    on_change=lambda value: UI.set_filter("order", value),
                                                    width="100%"), class_name="order-control"),
                                   rx.text(rx.match(UI.filters.get("order", "BPM flow"),
                                                    ("BPM ascending", "Start slow and build steadily."),
                                                    ("BPM descending", "Start fast and ease down."),
                                                    ("Best match", "Keep the search ranking."),
                                                    "Rise to a peak, then wind down. Tracks without BPM go last."),
                                           class_name="order-description"),
                                   class_name="filter-order-row"),
                            rx.hstack(*[rx.button(section, on_click=UI.set_filter_section(section),
                                                  variant="ghost", class_name=rx.cond(UI.filter_section == section,
                                                                                       "filter-tab is-active", "filter-tab"))
                                        for section in ("Sound", "Context", "Limits")], class_name="filter-tabs"),
                            rx.cond(UI.filter_section == "Sound",
                                rx.box(rx.box(filter_select("Genre", "genre", UI.genre_names),
                                              filter_input("Minimum BPM", "bpm_min"),
                                              filter_input("Maximum BPM", "bpm_max"),
                                              filter_select("Danceability", "danceability", ["low", "medium", "high"]),
                                              filter_input("Vocal tolerance", "vocal_tolerance", "0.55"),
                                              class_name="filter-grid"),
                                       rx.checkbox("Instrumental only", checked=UI.instrumental,
                                                   on_change=UI.set_instrumental),
                                       rx.hstack(rx.button("Genre families", rx.cond(UI.genre_families_open,
                                                                                      rx.icon("chevron-up", size=16),
                                                                                      rx.icon("chevron-down", size=16)),
                                                           on_click=UI.toggle_genre_families, variant="ghost",
                                                           aria_expanded=UI.genre_families_open,
                                                           class_name="genre-families-toggle"),
                                                 rx.cond(UI.buckets.length() > 0,
                                                         rx.badge(UI.buckets.length().to_string(), " selected"),
                                                         rx.fragment()),
                                                 class_name="genre-families-head"),
                                       rx.cond(UI.genre_families_open,
                                               rx.box(*[rx.checkbox(bucket, on_change=lambda enabled, b=bucket: UI.toggle_bucket(b, enabled))
                                                        for bucket in BUCKETS], class_name="bucket-grid"),
                                               rx.box()),
                                       class_name="filter-section"), rx.box()),
                            rx.cond(UI.filter_section == "Context",
                                rx.box(rx.box(filter_input("From year", "min_year"),
                                              filter_input("To year", "max_year"),
                                              filter_select("Country", "country", UI.country_names),
                                              filter_select("Gender", "gender", ["female", "male", "mixed"]),
                                              filter_select("Era", "era", ["50s", "60s", "70s", "80s", "90s", "00s", "10s", "20s"]),
                                              class_name="filter-grid"), class_name="filter-section"), rx.box()),
                            rx.cond(UI.filter_section == "Limits",
                                rx.box(rx.box(filter_input("Tracks", "limit"),
                                              filter_input("Tracks per artist", "max_per_artist"),
                                              filter_input("Minimum plays", "min_plays"),
                                              filter_input("Maximum plays", "max_plays"),
                                              filter_select("Minimum rating", "min_rating", ["2", "4", "6", "8", "10"]),
                                              class_name="filter-grid"),
                                       rx.checkbox("Unplayed only", checked=UI.unplayed,
                                                   on_change=UI.set_unplayed),
                                       class_name="filter-section"), rx.box()),
                            class_name="filter-content"),
                        rx.box()),
                    class_name="inline-filters"),
                class_name="home-prompt-panel"),
            class_name="home-feature"),
        rx.box(
            rx.box(rx.text("ANOTHER WAY IN", class_name="section-kicker"),
                   rx.heading("Start with something specific.", class_name="home-lower-title"),
                   rx.box(
                       rx.box(rx.heading("A track or artist", size="4"),
                              rx.text("Find a familiar sound and follow it somewhere new.", class_name="home-tool-copy"),
                              rx.hstack(rx.input(value=UI.based_on_query, on_change=UI.set_based_on_query,
                                                 placeholder="Search tracks or artists…"),
                                        rx.button("Search", on_click=UI.search_seed), class_name="home-tool-form"),
                              rx.box(rx.foreach(UI.suggestions,
                                                lambda item: rx.button(item["label"],
                                                                       on_click=UI.select_seed(item),
                                                                       variant="ghost", width="100%")),
                                     class_name="home-suggestions"),
                              class_name="home-tool"),
                       rx.box(rx.heading("A date worth revisiting", size="4"),
                              rx.text("Make a playlist from what you heard around that day.", class_name="home-tool-copy"),
                              rx.hstack(rx.input(type="date", value=UI.on_this_day,
                                                 on_change=UI.set_on_this_day),
                                        rx.button("Find tracks", on_click=UI.find_on_this_day),
                                        class_name="home-tool-form"),
                              class_name="home-tool"),
                       class_name="home-tools"),
                   class_name="home-ways"),
            rx.box(rx.hstack(rx.box(rx.text("ALREADY IN PLEX", class_name="section-kicker"),
                                   rx.heading("Your playlists", class_name="home-lower-title")),
                             rx.cond(UI.playlists.length() > 6,
                                     rx.button(rx.cond(UI.show_all_playlists, "Show fewer", "Show all"),
                                               on_click=UI.toggle_all_playlists, variant="ghost",
                                               class_name="home-playlist-toggle"),
                                     rx.fragment()),
                             justify="between", align="end", class_name="home-playlist-head"),
                   rx.text(UI.playlists.length(), " playlists in your library", class_name="home-playlist-count"),
                   rx.box(rx.foreach(UI.visible_playlists,
                                     lambda item: rx.hstack(rx.link(item["title"], href=item["url"], is_external=True),
                                                            rx.text(item["trackCount"].to_string(), class_name="home-playlist-size"),
                                                            class_name="playlist-row", justify="between")),
                          class_name="home-playlist-list"),
                   class_name="home-playlists"),
            class_name="home-lower"),
        rx.cond(UI.has_searched,
                rx.box(rx.hstack(rx.box(rx.text("READY TO MAKE", class_name="section-kicker"),
                                      rx.heading("Your draft playlist", class_name="home-lower-title")),
                                 rx.badge(UI.tracks.length().to_string(), " tracks"),
                                 justify="between", align="end", class_name="home-preview-head"),
                       rx.hstack(rx.foreach(UI.tags, lambda tag: rx.badge(tag)), class_name="home-preview-tags"),
                       rx.cond(UI.tracks.length() > 0,
                               rx.box(rx.box(rx.foreach(UI.tracks, track_row), class_name="track-list"),
                                      rx.hstack(rx.input(value=UI.playlist_name, on_change=UI.set_playlist_name,
                                                         placeholder="Playlist name"),
                                                rx.button("Create in Plex", on_click=UI.create_playlist,
                                                          disabled=UI.busy), class_name="home-create-row")),
                               rx.text("No tracks matched. Try a broader mood or loosen the filters.",
                                       class_name="home-empty-preview")),
                       class_name="home-preview"),
                rx.fragment()),
        rx.cond(UI.missing.length() > 0,
                rx.box(rx.heading("Scrobbled, but missing from your library", size="4"),
                       rx.foreach(UI.missing, lambda item: rx.text(item["artist"], " — ", item["title"])),
                       class_name="home-missing")),
        rx.box(rx.box(rx.text("YOUR COLLECTION, AT A GLANCE", class_name="home-stats-kicker"),
                      rx.heading("Every library has a pulse.", class_name="home-stats-title"),
                      rx.text("A few numbers behind the music you keep coming back to.",
                              class_name="home-stats-copy"),
                      rx.link("Explore the collection →", href="/stats", class_name="home-stats-link"),
                      class_name="home-stats-intro"),
               rx.box(home_stat("Tracks", "tracks", "ready to rediscover", "stat-mint"),
                      home_stat("Artists", "artists", "distinct voices", "stat-peach"),
                      home_stat("Listens", "plays", "moments remembered", "stat-gold"),
                      home_stat("Playlists", "playlists", "stories in order", "stat-blue"),
                      class_name="home-stats-grid"),
               class_name="home-stats-band"), show_intro=False)


def horizontal_chart(data, name_key: str, value_key: str, color: str = "#80532f"):
    return rx.recharts.bar_chart(
        rx.recharts.cartesian_grid(stroke="#ebe6dd", horizontal=False),
        rx.recharts.x_axis(type_="number", tick_line=False, axis_line=False),
        rx.recharts.y_axis(data_key=name_key, type_="category", width=135,
                           tick_line=False, axis_line=False),
        rx.recharts.graphing_tooltip(),
        rx.recharts.bar(data_key=value_key, fill=color, radius=[0, 6, 6, 0],
                        is_animation_active=True, animation_duration=900),
        data=data, layout="vertical", width="100%", height=320,
        margin={"top": 8, "right": 18, "bottom": 8, "left": 6},
    )


def vertical_chart(data, name_key: str, value_key: str, color: str = "#80532f"):
    return rx.recharts.bar_chart(
        rx.recharts.cartesian_grid(stroke="#ebe6dd", vertical=False),
        rx.recharts.x_axis(data_key=name_key, tick_line=False, axis_line=False),
        rx.recharts.y_axis(tick_line=False, axis_line=False),
        rx.recharts.graphing_tooltip(),
        rx.recharts.bar(data_key=value_key, fill=color, radius=[6, 6, 0, 0],
                        is_animation_active=True, animation_duration=900),
        data=data, width="100%", height=280,
        margin={"top": 8, "right": 12, "bottom": 8, "left": 4},
    )


def stats_metric(label: str, key: str, detail: str, accent: str):
    return rx.box(
        rx.text(label, class_name="metric-label"),
        rx.heading(UI.stats_display[key], class_name="metric-value"),
        rx.text(detail, class_name="metric-detail"),
        class_name=f"metric-card {accent}",
    )


def stats_chart(title: str, caption: str, chart, *, control=None, class_name: str = ""):
    return rx.box(
        rx.hstack(
            rx.box(rx.heading(title, class_name="chart-title"),
                   rx.text(caption, class_name="chart-caption")),
            control if control is not None else rx.box(),
            justify="between", align="start", class_name="chart-heading",
        ),
        chart,
        class_name=f"collection-chart {class_name}",
    )


def stats_limit(kind: str):
    state_value = {"artist": UI.artist_limit, "genre": UI.genre_limit,
                   "country": UI.country_limit}[kind]
    return rx.select(["10", "25", "50", "100"], value=state_value,
                     on_change=lambda value: UI.set_stats_limit(kind, value),
                     aria_label=f"Number of {kind} results", class_name="stats-limit")


def stats_page():
    return shell("The Collection", "A closer look at the music you keep and play.",
        rx.hstack(
            rx.box(rx.text("YOUR LIBRARY", class_name="section-kicker"),
                   rx.heading("In the stacks", class_name="collection-section-title"),
                   rx.text("An overview of your Plex library and Last.fm listening history.",
                           class_name="section-description")),
            rx.link("Export library CSV ↗", href="/export-csv", class_name="export-link"),
            justify="between", align="end", class_name="collection-intro",
        ),
        rx.box(
            stats_metric("Tracks", "total_tracks", "Songs in your Plex library", "metric-brown"),
            stats_metric("Artists", "total_artists", "Distinct artists to explore", "metric-sage"),
            stats_metric("Scrobbles", "total_scrobbles", "Plays recorded by Last.fm", "metric-terracotta"),
            stats_metric("Instrumentals", "total_instrumental", "Tracks without vocals", "metric-plum"),
            class_name="collection-metrics",
        ),
        rx.box(
            rx.text("LISTENING", class_name="section-kicker"),
            stats_chart("Your listening over time",
                rx.cond(UI.listening_granularity == "month", "Scrobbles by month", "Scrobbles by year"),
                rx.cond(UI.listening_by_year.length() > 0,
                    rx.recharts.line_chart(
                        rx.recharts.cartesian_grid(stroke="#e8e4db", vertical=False),
                        rx.recharts.x_axis(data_key=UI.listening_granularity, tick_line=False, axis_line=False),
                        rx.recharts.y_axis(tick_line=False, axis_line=False),
                        rx.recharts.graphing_tooltip(),
                        rx.recharts.line(data_key="plays", stroke="#80532f", stroke_width=3,
                                         type_="monotone", dot=True,
                                         is_animation_active=True, animation_duration=900),
                        data=rx.cond(UI.listening_granularity == "month",
                                     UI.listening_by_month, UI.listening_by_year),
                        width="100%", height=300,
                        margin={"top": 12, "right": 18, "bottom": 4, "left": -18}),
                    rx.box(rx.text("No listening history yet."),
                           rx.text("Sync Last.fm from Admin to see your plays by year.",
                                   class_name="empty-hint"), class_name="empty-chart")),
                class_name="chart-feature"),
            class_name="collection-section",
        ),
        rx.box(
            rx.text("DISCOVER", class_name="section-kicker"),
            rx.heading("What makes up your collection", class_name="collection-section-title"),
            rx.box(
                stats_chart("Most played artists", "Artists by Plex play count",
                    rx.cond(UI.top_artists.length() > 0,
                        horizontal_chart(UI.top_artists, "artist", "plays"),
                        rx.text("Play counts will appear after a library sync.", class_name="empty-chart")),
                    control=stats_limit("artist")),
                stats_chart("Where the music comes from", "Artist origins in your library",
                    rx.cond(UI.by_country.length() > 0,
                        horizontal_chart(UI.by_country, "country", "cnt", "#567264"),
                        rx.text("Country data will appear after enrichment.", class_name="empty-chart")),
                    control=stats_limit("country")),
                stats_chart("Genres",
                    rx.cond(UI.genre_source == "plex", "Genres from Plex library metadata",
                            "Enriched tags across your tracks"),
                    rx.cond(UI.top_genres.length() > 0,
                        horizontal_chart(UI.top_genres, "tag", "cnt", "#927082"),
                        rx.box(rx.text("No tagged genres yet."),
                               rx.link("Run the tagger in Admin →", href="/admin"),
                               class_name="empty-chart")),
                    control=stats_limit("genre")),
                stats_chart("Across the decades", "Artists by era",
                    rx.cond(UI.by_era.length() > 0,
                        vertical_chart(UI.by_era, "era", "cnt", "#b47b46"),
                        rx.text("Era data will appear after enrichment.", class_name="empty-chart"))),
                stats_chart("Artist gender", "Metadata for artists in your library",
                    rx.cond(UI.by_gender.length() > 0,
                        rx.recharts.pie_chart(
                            rx.recharts.graphing_tooltip(),
                            rx.recharts.pie(
                                rx.foreach(UI.by_gender,
                                    lambda item, index: rx.recharts.cell(
                                        fill=rx.match(index, (0, "#80532f"),
                                                      (1, "#567264"),
                                                      (2, "#a56643"),
                                                      "#927082"))),
                                data=UI.by_gender, data_key="cnt", name_key="gender",
                                cx="50%", cy="46%", outer_radius=88, label=True,
                                is_animation_active=True, animation_duration=1000),
                            rx.recharts.legend(),
                            width="100%", height=300, class_name="gender-chart"),
                        rx.text("Gender data will appear after enrichment.", class_name="empty-chart"))),
                class_name="collection-charts",
            ), class_name="collection-section",
        ),
    )


JOB_LABELS = [("fullsync", "Full Sync"), ("ingest", "Sync Plex Library"),
              ("lastfm", "Sync Last.fm"), ("tagger", "Tag tracks"),
              ("context", "Listening context"), ("mbenrich", "MusicBrainz enrichment"),
              ("aienrich", "AI enrichment"), ("gaps", "Find collection gaps"),
              ("fingerprint", "Fingerprint tracks"), ("copyforward", "Copy forward analysis"),
              ("dedup", "Duplicate report"), ("varesolve", "Resolve Various Artists"),
              ("recordingmbid", "Resolve recording IDs"), ("synapse", "Synapse analysis")]


def _job_label(name: str) -> str:
    labels = dict(JOB_LABELS)
    labels["synapse_full"] = "Synapse audio analysis"
    labels["synapse_limited"] = "Limited Synapse analysis"
    labels["synapse_count"] = "Synapse track count"
    labels["synapse_estimate"] = "Synapse time estimate"
    return labels.get(name, name.replace("_", " ").title())


def synapse_running_indicator():
    active = UI.running_jobs.contains("synapse_full")
    return rx.box(
        rx.cond(
            active,
            rx.hstack(rx.icon("activity", size=15), rx.text("Running")),
            rx.hstack(rx.icon("circle-check", size=15), rx.text("Idle")),
        ),
        class_name=rx.cond(active, "synapse-run-indicator is-running", "synapse-run-indicator"),
        role="status", aria_live="polite",
    )


def fullsync_blocked():
    return (
        UI.running_jobs.contains("ingest")
        | UI.running_jobs.contains("fingerprint")
        | UI.running_jobs.contains("copyforward")
        | UI.running_jobs.contains("varesolve")
        | UI.running_jobs.contains("recordingmbid")
        | UI.running_jobs.contains("lastfm")
        | UI.running_jobs.contains("mbenrich")
        | UI.running_jobs.contains("aienrich")
        | UI.running_jobs.contains("tagger")
        | UI.running_jobs.contains("synapse")
        | UI.running_jobs.contains("synapse_full")
        | UI.running_jobs.contains("synapse_limited")
        | UI.running_jobs.contains("group_library")
        | UI.running_jobs.contains("group_enrichment")
        | UI.running_jobs.contains("group_analysis")
        | UI.running_jobs.contains("group_maintenance")
    )


JOB_GROUPS = [
    ("Library", "Run individual library and listening-history updates.", [
        ("ingest", "Sync Plex library", "Imports Plex's current library into MusicMind's local index."),
        ("lastfm", "Sync Last.fm", "Updates listening history and recent play counts."),
    ]),
    ("Enrichment", "Add descriptive metadata used by search, charts, and playlist matching.", [
        ("mbenrich", "MusicBrainz enrichment", "Matches artists to verified MusicBrainz records."),
        ("aienrich", "AI enrichment", "Fills remaining artist and track metadata."),
        ("tagger", "Tag tracks", "Generates specific genre and mood tags for tracks."),
        ("context", "Listening context", "Adds context signals to Last.fm listening history."),
        ("recordingmbid", "Resolve recording IDs", "Matches tracks to MusicBrainz recording IDs."),
    ]),
    ("Analysis", "Run audio and collection analysis used by insights and recommendations.", [
        ("gaps", "Find collection gaps", "Finds frequently played artists missing from Plex."),
        ("fingerprint", "Fingerprint tracks", "Identifies recordings from their audio fingerprints."),
        ("copyforward", "Copy forward analysis", "Reuses valid analysis for matching tracks."),
    ]),
    ("Maintenance", "Review duplicates and clean up artist identities.", [
        ("dedup", "Duplicate report", "Finds likely duplicate tracks and albums."),
        ("varesolve", "Resolve Various Artists", "Repairs compilation artist attribution."),
    ]),
]


def job_status_dialog():
    return rx.dialog.root(
        rx.dialog.content(
            rx.hstack(
                rx.box(rx.dialog.title(UI.selected_job_label),
                       rx.text("Live job status and recent output.", class_name="job-dialog-hint"),
                       class_name="job-dialog-heading"),
                rx.hstack(
                    rx.cond(UI.job_running, rx.badge("Running", color_scheme="green"),
                            rx.badge("Idle")),
                    rx.cond(UI.job_running,
                            rx.button("Stop", on_click=UI.stop_job(UI.selected_job), color_scheme="red"),
                            rx.fragment()),
                    rx.button("Refresh", on_click=UI.job_load, variant="outline"),
                    rx.button("Close", on_click=UI.set_job_dialog_open(False), variant="outline"),
                    class_name="job-dialog-actions"),
                justify="between", align="start", class_name="job-dialog-header"),
            rx.cond(UI.selected_job == "fullsync",
                    rx.box(rx.text(UI.fullsync_phase, class_name="job-dialog-phase"),
                           rx.progress(value=UI.fullsync_progress, max=100, size="2",
                                       class_name="fullsync-progress"),
                           rx.text(UI.fullsync_step.to_string() + " of 12 stages",
                                   class_name="job-dialog-progress-label"),
                           class_name="job-dialog-progress"),
                    rx.fragment()),
            rx.box(UI.job_log, class_name="job-dialog-log"),
            class_name="job-dialog-content", size="3"),
        open=UI.job_dialog_open,
        on_open_change=UI.set_job_dialog_open
    )


def synapse_network_svg() -> str:
    """An irregular point field with a separate animated signal layer."""
    rng = Random(23)
    points = []
    while len(points) < 64:
        point = (round(rng.uniform(320, 1020)), round(rng.uniform(-28, 390)))
        if all((point[0] - x) ** 2 + (point[1] - y) ** 2 > 34 ** 2
               for x, y in points):
            points.append(point)
    edges = set()
    for i, (x, y) in enumerate(points):
        neighbors = sorted(
            (j for j in range(len(points)) if j != i),
            key=lambda j: (points[j][0] - x) ** 2 + (points[j][1] - y) ** 2,
        )[:3]
        edges.update(tuple(sorted((i, j))) for j in neighbors
                     if (points[j][0] - x) ** 2 + (points[j][1] - y) ** 2 < 145 ** 2)
    lines = "".join(
        f'<line x1="{points[i][0]}" y1="{points[i][1]}" '
        f'x2="{points[j][0]}" y2="{points[j][1]}"/>'
        for i, j in sorted(edges)
    )
    nodes = "".join(
        f'<g class="synapse-node" style="--pulse-delay:{i % 11 * -.31:.2f}s">'
        f'<circle class="synapse-halo" cx="{x}" cy="{y}" r="{11 if i % 5 == 0 else 7}"/>'
        f'<circle class="synapse-point" cx="{x}" cy="{y}" r="{4 if i % 9 == 0 else 2 if i % 3 else 2.8}"/>'
        '</g>'
        for i, (x, y) in enumerate(points)
    )
    return (
        '<svg viewBox="0 0 1000 360" preserveAspectRatio="xMidYMid slice" '
        'xmlns="http://www.w3.org/2000/svg" '
        'aria-hidden="true" focusable="false">'
        f'<g class="synapse-lines">{lines}</g>'
        f'<g class="synapse-signals">{lines}</g>'
        f'{nodes}</svg>'
    )


def admin_page():
    return shell("Back Office", "Run maintenance and follow each job's output.",
                 rx.box(
                     rx.hstack(
                         rx.box(rx.text("MUSICMIND / ADMIN", class_name="admin-eyebrow"),
                                rx.text("A little order in the noise.", class_name="admin-signature")),
                         justify="between", align="center", class_name="admin-utility-header"),
                     rx.box(
                         rx.box(
                             rx.box(rx.icon("folder-sync", size=22), class_name="admin-tool-icon"),
                             rx.box(rx.heading("Find new music", size="4"),
                                    rx.text("Ask Plex to look for new or changed files in your music folders.",
                                            class_name="admin-tool-copy"),
                                    rx.text("Then run Full sync below to bring those changes into MusicMind.",
                                            class_name="admin-tool-note"),
                                    rx.button("Scan Plex folders", rx.icon("arrow-up-right", size=15),
                                              on_click=UI.scan_plex, variant="outline"),
                                    class_name="admin-tool-body"),
                             class_name="admin-library-tool"),
                         rx.box(
                             rx.box(rx.icon("refresh-cw", size=22), class_name="admin-tool-icon"),
                             rx.box(rx.heading("Refresh a specific release", size="4"),
                                    rx.text("Recheck one artist or album without refreshing the whole library.",
                                            class_name="admin-tool-copy"),
                                    rx.box(
                                        rx.box(rx.text("Artist", as_="label", html_for="resync-artist"),
                                               rx.input(id="resync-artist", value=UI.resync_artist,
                                                        on_change=UI.set_resync_artist, placeholder="Artist name")),
                                        rx.box(rx.text("Album", as_="label", html_for="resync-album"),
                                               rx.input(id="resync-album", value=UI.resync_album,
                                                        on_change=UI.set_resync_album, placeholder="Album title")),
                                        class_name="admin-resync-fields"),
                                    rx.hstack(
                                        rx.checkbox("Apply changes", checked=UI.resync_apply,
                                                    on_change=UI.set_resync_apply),
                                        rx.button(rx.cond(UI.resync_apply, "Refresh release", "Preview changes"),
                                                  on_click=UI.start_resync,
                                                  disabled=(UI.resync_artist == "") | (UI.resync_album == "")),
                                        justify="between", align="center", class_name="admin-resync-actions"),
                                    rx.text("Preview shows what will change before you apply it.",
                                            class_name="admin-tool-note"),
                                    class_name="admin-tool-body"),
                             class_name="admin-library-tool"),
                         class_name="admin-library-tools"),
                     class_name="admin-workspace"),
                 rx.text("LIBRARY OPERATIONS", class_name="section-kicker"),
                 rx.heading("Keep your collection in tune", class_name="admin-operations-title"),
                 rx.text("Run the complete pipeline, analyze audio, or choose an individual task below.",
                         class_name="admin-operations-copy"),
                 panel("Full sync",
                       rx.text("Refresh the Plex index, listening history, metadata, tags, and audio analysis.",
                               class_name="fullsync-description"),
                       rx.hstack(
                           rx.cond(UI.running_jobs.contains("fullsync"),
                                   rx.badge("Running", color_scheme="green"),
                                   rx.badge("Idle")),
                           rx.text(UI.fullsync_phase, class_name="fullsync-phase"),
                           class_name="fullsync-status-row"),
                       rx.progress(value=UI.fullsync_progress, max=100, size="2",
                                   class_name="fullsync-progress"),
                       rx.text(UI.fullsync_step.to_string() + " of 12 stages",
                               class_name="fullsync-progress-label"),
                       rx.cond(fullsync_blocked(),
                               rx.text("Another pipeline job is active. Full sync can start when it finishes.",
                                       class_name="fullsync-blocked-note"),
                               rx.fragment()),
                       rx.hstack(
                           rx.button("Start full sync", on_click=UI.start_job("fullsync"),
                                     disabled=UI.running_jobs.contains("fullsync") | fullsync_blocked()),
                           rx.button("Status", on_click=UI.select_job("fullsync"), variant="outline"),
                           rx.cond(UI.running_jobs.contains("fullsync"),
                                   rx.button("Stop", on_click=UI.stop_job("fullsync"), color_scheme="red"),
                                   rx.fragment()),
                           class_name="fullsync-actions"),
                       class_name="panel fullsync-tracker"),
                 rx.el.div(id="synapse", class_name="admin-section-anchor"),
                 panel("Synapse audio analysis",
                       rx.box(
                           rx.box(synapse_running_indicator(),
                                  rx.text("Measure tempo, key, and vocal features across your tracks.",
                                          class_name="synapse-summary"),
                                  rx.hstack(
                                      rx.box(rx.text("ANALYZED", class_name="synapse-metric-label"),
                                             rx.text(UI.synapse.get("analyzed", 0).to_string(), class_name="synapse-metric-value"),
                                             class_name="synapse-metric"),
                                      rx.box(rx.text("ERRORS", class_name="synapse-metric-label"),
                                             rx.text(UI.synapse.get("errors", 0).to_string(), class_name="synapse-metric-value"),
                                             class_name="synapse-metric error-metric"),
                                      class_name="synapse-metrics"),
                                  rx.hstack(rx.button("Start analysis", on_click=UI.start_job("synapse_full")),
                                            rx.button("Count tracks", on_click=UI.start_job("synapse_count"), variant="outline"),
                                            rx.button("Status", on_click=UI.select_job("synapse_full"), variant="outline"),
                                            class_name="synapse-admin-actions"),
                                  class_name="synapse-admin-main"),
                           rx.box(rx.html(synapse_network_svg()),
                                  class_name=rx.cond(UI.running_jobs.contains("synapse_full") |
                                                     UI.running_jobs.contains("synapse_limited"),
                                                     "synapse-neuron is-active", "synapse-neuron"),
                                  aria_hidden="true"),
                           class_name="synapse-admin-layout"),
                       class_name="panel synapse-admin-panel"),
                 rx.text("INDIVIDUAL TASKS", class_name="section-kicker admin-tasks-kicker"),
                 rx.box(*[
                     rx.el.details(rx.el.summary(rx.hstack(
                                rx.box(rx.heading(group, size="4", class_name="job-group-title"),
                                       rx.text(description, class_name="job-group-description"),
                                       class_name="job-group-intro"),
                                rx.hstack(
                                    rx.cond(UI.running_jobs.contains(f"group_{group.lower()}"),
                                            rx.badge("Running", color_scheme="green"),
                                            rx.fragment()),
                                    rx.button("Run all", on_click=UI.start_job(f"group_{group.lower()}"),
                                              disabled=UI.running_jobs.contains(f"group_{group.lower()}") |
                                              UI.running_jobs.contains("fullsync")),
                                    rx.box(rx.icon("chevron-down", size=18),
                                           class_name="job-group-toggle", aria_hidden="true"),
                                    class_name="job-group-controls"),
                                class_name="job-group-header", justify="between", align="center")),
                            rx.box(*[
                                rx.box(rx.box(rx.text(label, class_name="job-name"),
                                              rx.text(detail, class_name="job-description"),
                                              class_name="job-copy"),
                                       rx.hstack(
                                           rx.cond(UI.running_jobs.contains(name),
                                                   rx.badge("Running", color_scheme="green",
                                                            class_name="job-running-badge"),
                                                   rx.badge("Idle", class_name="job-idle-badge")),
                                           rx.button("Run", on_click=UI.start_job(name),
                                                     disabled=UI.running_jobs.contains(f"group_{group.lower()}") |
                                                     UI.running_jobs.contains("fullsync")),
                                           rx.button("Status", on_click=UI.select_job(name), variant="outline"),
                                           class_name="job-actions"),
                                       class_name="job-entry")
                                for name, label, detail in items
                                if LASTFM_KEY or name != "lastfm"],
                                  class_name="job-list", id=f"{group.lower()}-job-list"),
                            class_name="job-group")
                     for group, description, items in JOB_GROUPS],
                     class_name="job-groups"),
                 job_status_dialog())


def logs_page():
    return shell("Query Logs", "Recent searches, errors, and AI usage.",
                 panel("Recent queries", rx.button("Refresh", on_click=UI.logs_load),
                       rx.foreach(UI.logs, lambda entry: rx.box(
                           rx.hstack(rx.text(entry["timestamp"]), rx.text(entry["prompt"]),
                                     rx.badge(entry["count"].to_string()), justify="between"),
                           rx.cond(entry["error"] != "", rx.text(entry["error"], color="red")),
                           class_name="log-entry"))))


def query_page():
    return shell("Database", "Read-only SQL for your MusicMind library.",
                 panel("Query", rx.text_area(value=UI.sql, on_change=UI.set_sql, width="100%"),
                       rx.button("Run query", on_click=UI.run_query, disabled=UI.busy)),
                 panel("Results", rx.hstack(rx.foreach(UI.query_columns, lambda col: rx.badge(col))),
                       rx.foreach(UI.query_rows, lambda row: rx.hstack(
                           rx.foreach(row, lambda cell: rx.text(cell)), class_name="query-row"))))


def gaps_page():
    return shell("Missing from Your Collection", "Discover what belongs in your library.",
        rx.box(rx.text("COLLECTION GAPS", class_name="section-kicker"),
               rx.heading("Worth another listen.", size="7"),
               rx.text("Artists you’ve played at least 50 times on Last.fm that are missing from your Plex library.",
                       class_name="gaps-intro-copy"),
               rx.hstack(rx.badge(UI.gaps.length().to_string() + " missing artists"),
                         rx.button("Refresh list", on_click=UI.gaps_load, variant="outline"),
                         align="center", gap="3"), class_name="gaps-intro"),
        rx.foreach(UI.gap_buckets, lambda bucket:
            rx.el.details(
                rx.el.summary(rx.hstack(
                    rx.box(rx.heading(bucket["label"].to(str), size="4"),
                           rx.text(bucket["description"].to(str), class_name="gap-category-copy")),
                    rx.hstack(rx.text(bucket["count"].to_string() + " artists"),
                              rx.icon("chevron-down", size=18), align="center", gap="3"),
                    justify="between", align="center")),
                rx.cond(bucket["count"].to(int) > 0,
                    rx.box(rx.foreach(bucket["artists"].to(list[dict]), lambda artist:
                        rx.hstack(rx.text(artist["artist"].to(str)),
                                  rx.text(artist["scrobbles"].to_string() + " plays", class_name="gap-play-count"),
                                  justify="between", class_name="gap-artist-row")), class_name="gap-artists"),
                    rx.text("No missing artists in this category.", class_name="gap-category-copy")),
                open=bucket["key"] == "worth_acquiring", class_name="gap-category")),
        rx.cond(UI.gaps.length() == 0,
            rx.text("No gaps recorded yet. Run Find collection gaps under Admin → Individual tasks → Analysis.",
                    class_name="gaps-empty"), rx.fragment()))


def audit_page():
    return shell("Playlist Audit", "Inspect the tracks behind a Plex playlist.",
                 panel("Select playlist",
                     rx.hstack(rx.input(value=UI.playlist_key, on_change=UI.set_playlist_key,
                                        placeholder="Playlist key"),
                               rx.button("Inspect", on_click=UI.audit_load)),
                     rx.box(rx.foreach(UI.playlists, lambda p: rx.button(p["title"],
                         on_click=UI.select_playlist(p["key"].to(str)),
                         variant="outline", class_name="playlist-choice")),
                         class_name="playlist-choices")),
                 rx.cond(UI.audit.contains("title"),
                     panel("Playlist analysis",
                         rx.heading(UI.audit.get("title", ""), size="5"),
                         rx.cond(UI.audit.get("summary", ""),
                                 rx.text(UI.audit.get("summary", ""), class_name="audit-summary"), rx.fragment()),
                         rx.text(UI.audit_tracks.length().to_string() + " tracks · — means analysis is unavailable",
                                 class_name="audit-caption"),
                         rx.box(rx.table.root(
                             rx.table.header(rx.table.row(*[rx.table.column_header_cell(label)
                                 for label in ["#", "Track", "Artist", "BPM", "Danceability", "Voice probability", "Classification"]])),
                             rx.table.body(rx.foreach(UI.audit_tracks, lambda track: rx.table.row(
                                 *[rx.table.cell(track[key]) for key in
                                   ["number", "title", "artist", "bpm", "danceability", "voice", "verdict"]]))),
                             width="100%"), class_name="audit-table")),
                     rx.text("Select a playlist to inspect its tracks and audio analysis.", class_name="audit-caption")))


def update_page():
    return shell("Update", "Check whether a newer MusicMind release is available.",
                 panel("Repository status", rx.button("Check for updates", on_click=UI.update_load),
                       rx.code_block(UI.update_info.to_string(), language="json")))


def tests_page():
    return shell("Tests", "Check library integrity and enrichment results.",
                 panel("Script tests", rx.box(*[
                     rx.box(rx.hstack(rx.heading(label, size="3"),
                                      rx.button("Run test", on_click=UI.start_job(key)),
                                      justify="between", align="center", class_name="test-row-head"),
                            rx.text(detail, class_name="test-description"),
                            class_name="test-card")
                     for key, label, detail in [
                         ("mb_dry_run", "🔍 MusicBrainz — Dry Run",
                          "Checks three artists without writing to the database."),
                         ("mb_limited_run", "🔍 MusicBrainz — Limited Real Run",
                          "Enriches at most one artist, or reports that none need enrichment."),
                         ("ai_dry_run", "🤖 AI Fallback — Dry Run",
                          "Checks three artists without writing to the database."),
                         ("ai_limited_run", "🤖 AI Fallback — Limited Real Run",
                          "Updates at most one artist, or reports that none need enrichment."),
                     ]], class_name="test-grid")),
                 panel("Data integrity checks",
                       rx.text("Instant database checks. These do not change any data.",
                               class_name="test-description"),
                       rx.box(*[rx.box(rx.text(label, class_name="test-check-label"),
                                      rx.button("Check", on_click=UI.run_assertion(key)),
                                      class_name="test-check")
                                for key, label in [
                                    ("mbid_has_country", "Every MusicBrainz artist has a country"),
                                    ("no_null_era", "No artist has a missing era value"),
                                    ("unmatched_artists_not_in_meta",
                                     "No artist is both matched and marked unmatched"),
                                ]], class_name="test-check-list")),
                 panel("Result", rx.code_block(UI.audit.to_string(), language="json")),
                 panel("Test output", rx.button("Refresh", on_click=UI.job_load),
                       rx.code_block(UI.job_log, language="text")))


def guide_page():
    return shell("Guide", "How to get the most from MusicMind.",
                 home_art(),
                 rx.box(rx.markdown(UI.guide_text), class_name="guide-prose"))


api = FastAPI(title="MusicMind for Plex")
api.mount("/static", StaticFiles(directory=PROJECT_ROOT / "web" / "static"), name="static")


def _dispatch_legacy(method: str, path: str, body: bytes, content_type: str):
    from web.app import app as flask_app

    client = flask_app.test_client()
    result = client.open(path, method=method, data=body, content_type=content_type, buffered=False)
    if result.mimetype == "text/event-stream":
        return result
    response = Response(content=result.get_data(), status_code=result.status_code,
                        media_type=result.mimetype)
    result.close()
    return response


async def legacy_api(request: Request):
    path = request.url.path + ("?" + request.url.query if request.url.query else "")
    response = await asyncio.to_thread(
        _dispatch_legacy, request.method, path, await request.body(),
        request.headers.get("content-type", "application/octet-stream"))
    if isinstance(response, Response):
        return response

    def chunks():
        try:
            yield from response.response
        finally:
            response.close()

    return StreamingResponse(chunks(), status_code=response.status_code,
                             media_type="text/event-stream")


LEGACY_API = [
    ("/preview", ["POST"]), ("/create", ["POST"]),
    ("/onthisday", ["POST"]), ("/based-on", ["POST"]),
    ("/based-on-search", ["GET"]), ("/query", ["POST"]),
    ("/playlists", ["GET"]), ("/genres", ["GET"]),
    ("/countries", ["GET"]), ("/stats/data", ["GET"]),
    ("/export-csv", ["GET"]), ("/scan", ["GET"]),
    ("/playlist-audit-data/{playlist_key}", ["GET"]),
    ("/check-update", ["GET"]),
    ("/admin/error-counts", ["GET"]),
    ("/admin/clear-errors/{source}", ["POST"]),
    ("/admin/other-processes-status", ["GET"]),
    ("/synapse-status", ["GET"]), ("/synapse-errors", ["GET"]),
    ("/synapse-full-log", ["GET"]),
    ("/run/fullsync-tail", ["GET"]), ("/run/synapse-full", ["GET"]),
    ("/run/synapse-count", ["GET"]), ("/run/synapse-estimate", ["GET"]),
    ("/run/synapse-limited", ["GET"]), ("/run/resync", ["GET"]),
    ("/run/gaps", ["GET"]), ("/run/fullsync", ["GET"]),
    ("/run/update", ["GET"]),
    ("/run/assertion/{assertion_id}", ["GET"]),
    ("/run/test/{test_id}", ["GET"]),
    ("/run/{script}", ["GET"]),
]
for route, methods in LEGACY_API:
    api.add_api_route(route, legacy_api, methods=methods, include_in_schema=False)


app = rx.App(
    api_transformer=api,
    stylesheets=["/reflex.css"],
)
for page, route, on_load in [
    (home, "/", UI.home_load),
    (stats_page, "/stats", UI.stats_load),
    (admin_page, "/admin", UI.admin_load),
    (lambda: rx.fragment(), "/synapse", rx.redirect("/admin")),
    (logs_page, "/logs", UI.logs_load),
    (query_page, "/db", None),
    (gaps_page, "/gaps", UI.gaps_load),
    (audit_page, "/playlist-audit", UI.playlists_load),
    (update_page, "/update", UI.update_load),
    (tests_page, "/tests", None),
    (guide_page, "/guide", UI.guide_load),
]:
    app.add_page(page, route=route,
                 on_load=[UI.clear_message, on_load] if on_load else UI.clear_message)
