"""Logs, database, gaps, audit, update, tests, and guide pages."""

import reflex as rx
from musicmind_ui.state import UI
from .components import panel, shell
from .home import home_art


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


