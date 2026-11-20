"""Admin and background job pages."""

from random import Random

import reflex as rx
from musicmind_ui.job_definitions import JOB_GROUPS
from musicmind_ui.state import LASTFM_KEY, UI
from .components import panel, shell



def synapse_running_indicator():
    active = UI.running_jobs.contains("synapse_full") | UI.running_jobs.contains("synapse_limited")
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
        | UI.running_jobs.contains("plex_history")
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


def job_status_dialog():
    return rx.dialog.root(
        rx.dialog.content(
            rx.hstack(
                rx.box(rx.dialog.title(UI.selected_job_label),
                       rx.text("Live job status and recent output.", class_name="job-dialog-hint"),
                       class_name="job-dialog-heading"),
                rx.hstack(
                    rx.badge(UI.job_state, role="status"),
                    rx.cond(UI.job_running,
                            rx.button("Stop", on_click=UI.stop_job(UI.selected_job), color_scheme="red"),
                            rx.fragment()),
                    rx.button("Refresh", on_click=UI.job_load, variant="outline"),
                    rx.button("Close", on_click=UI.set_job_dialog_open(False), variant="outline"),
                    class_name="job-dialog-actions"),
                justify="between", align="start", class_name="job-dialog-header"),
            rx.cond((UI.selected_job == "fullsync") & UI.job_running,
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


def job_entry(name, label, detail, group="Library"):
    blocked = UI.running_jobs.contains(f"group_{group.lower()}") | UI.running_jobs.contains("fullsync")
    return rx.box(
        rx.box(rx.text(label, class_name="job-name"), rx.text(detail, class_name="job-description"),
               rx.text(UI.job_errors.get(name, ""), role="status", class_name="admin-feedback"), class_name="job-copy"),
        rx.hstack(rx.badge(UI.job_states.get(name, "Loading status")),
                  rx.button("Run task", on_click=UI.start_job(name),
                            disabled=blocked | UI.running_jobs.contains(name) | UI.pending_jobs.contains(name),
                            loading=UI.pending_jobs.contains(name)),
                  rx.button("View details", on_click=UI.select_job(name), variant="outline"),
                  class_name="job-actions"),
        rx.cond(blocked, rx.text("Full sync or this task group is running.", class_name="admin-feedback"), rx.fragment()),
        class_name="job-entry")


def admin_page():
    all_jobs = [("fullsync", "Full sync"), ("synapse_full", "Audio analysis"),
                ("synapse_limited", "Limited audio analysis"), ("synapse_count", "Count tracks"),
                ("resync", "Album refresh")]
    all_jobs += [(name, label) for _, _, items in JOB_GROUPS for name, label, _ in items]
    all_jobs += [(f"group_{group.lower()}", group + " tasks") for group, _, _ in JOB_GROUPS]
    return shell("Admin", "", rx.box(
        rx.box(rx.heading("Admin", as_="h1", class_name="admin-page-title"),
               rx.text("Sync your library, manage metadata, and follow background jobs."),
               rx.hstack(*[rx.link(label, href=f"#{anchor}") for label, anchor in [
                   ("Overview", "overview"), ("Library Operations", "library-operations"),
                   ("Library tools", "library-tools"), ("Data transfers", "data-transfers"),
                   ("Advanced tasks", "advanced-tasks")]], class_name="admin-local-nav"),
               id="overview", class_name="admin-intro"),
        rx.box(rx.hstack(rx.icon("activity", size=16, aria_hidden="true"),
                         rx.heading("Activity", as_="h2", size="3"),
                         rx.cond(UI.running_jobs.length() == 0,
                                 rx.text("No jobs running", class_name="admin-activity-summary"),
                                 rx.text(UI.running_jobs.length().to_string() + " jobs running",
                                         class_name="admin-activity-summary")),
                         class_name="admin-activity-heading"),
               *[rx.cond(UI.running_jobs.contains(name),
                         rx.hstack(rx.text(label), rx.badge("Running"),
                                   rx.button("View details", on_click=UI.select_job(name), variant="outline"),
                                   class_name="admin-activity-row"), rx.fragment()) for name, label in all_jobs],
               class_name="admin-activity", role="status"),
        rx.text("KEEP YOUR LIBRARY CURRENT", class_name="section-kicker"),
        panel("Full sync", rx.text("Scans Plex folders and waits for the scan to finish, then refreshes the Plex index, listening history, metadata, tags, and audio analysis.", class_name="fullsync-description"),
              rx.badge(UI.job_states.get("fullsync", "Loading status")),
              rx.cond(UI.running_jobs.contains("fullsync"), rx.box(rx.text(UI.fullsync_phase),
                      rx.progress(value=UI.fullsync_progress, max=100, class_name="fullsync-progress"),
                      rx.text("Stage " + UI.fullsync_step.to_string() + " of 12")), rx.fragment()),
              rx.cond(fullsync_blocked(), rx.text("Another pipeline job is active. Full sync can start when it finishes.", class_name="admin-feedback"), rx.fragment()),
              rx.text(UI.job_errors.get("fullsync", ""), role="status", class_name="admin-feedback"),
              rx.hstack(rx.button("Start full sync", on_click=UI.start_job("fullsync"),
                                  disabled=UI.running_jobs.contains("fullsync") | fullsync_blocked() | UI.pending_jobs.contains("fullsync"),
                                  loading=UI.pending_jobs.contains("fullsync")),
                        rx.button("View details", on_click=UI.select_job("fullsync"), variant="outline"), class_name="fullsync-actions"), class_name="panel fullsync-tracker"),
        rx.el.details(rx.el.summary(
                          rx.heading("Library Operations", as_="h2", size="4"),
                          rx.icon("chevron-down", size=20, class_name="library-operations-chevron",
                                  aria_hidden="true")),
                      rx.box(*[job_entry(name, label, detail) for group, _, items in JOB_GROUPS if group == "Library"
                               for name, label, detail in items if LASTFM_KEY or name != "lastfm"], class_name="job-list"),
                      rx.cond(not bool(LASTFM_KEY), rx.text("Last.fm sync is unavailable until the integration is configured."), rx.fragment()),
                      id="library-operations", class_name="job-group admin-section"),
        rx.box(rx.heading("Library tools", as_="h2", size="5"),
               rx.box(panel("Scan Plex folders", rx.text("Request file discovery in Plex. Sync Plex library imports the current Plex index."),
                            rx.button("Scan Plex folders", on_click=UI.scan_plex, variant="outline")),
                      panel("Refresh an album", rx.text("Preview a refresh for one artist and album."),
                            rx.box(rx.box(rx.text("Artist", as_="label", html_for="resync-artist"), rx.input(id="resync-artist", value=UI.resync_artist, on_change=UI.set_resync_artist)),
                                   rx.box(rx.text("Album", as_="label", html_for="resync-album"), rx.input(id="resync-album", value=UI.resync_album, on_change=UI.set_resync_album)), class_name="admin-resync-fields"),
                            rx.hstack(rx.button("Preview changes", on_click=UI.start_resync(False), disabled=UI.pending_jobs.contains("resync") | UI.running_jobs.contains("resync")),
                                      rx.cond(UI.resync_preview_ready, rx.button("Apply changes", on_click=UI.start_resync(True)), rx.fragment()),
                                      rx.button("View preview log", on_click=UI.select_job("resync"), variant="outline"), class_name="admin-resync-actions"),
                            rx.text("The preview log is not an atomic snapshot; the result may change before applying."),
                            rx.text(UI.job_states.get("resync", "")), rx.text(UI.job_errors.get("resync", ""), role="status")),
                      class_name="admin-library-tools"),
               rx.box(panel("Synapse audio analysis",
                     rx.box(
                         rx.box(synapse_running_indicator(),
                                rx.text("Measure tempo, key, and vocal features across your tracks.", class_name="synapse-summary"),
                                rx.hstack(
                                    rx.box(rx.text("ANALYZED TRACKS", class_name="synapse-metric-label"),
                                           rx.text(UI.synapse.get("analyzed", "Unavailable").to_string(), class_name="synapse-metric-value"), class_name="synapse-metric"),
                                    rx.box(rx.text("ERRORS", class_name="synapse-metric-label"),
                                           rx.text(UI.synapse.get("errors", "Unavailable").to_string(), class_name="synapse-metric-value"), class_name="synapse-metric error-metric"),
                                    class_name="synapse-metrics"),
                                rx.hstack(rx.button("Start analysis", on_click=UI.start_job("synapse_full"), disabled=UI.pending_jobs.contains("synapse_full") | UI.running_jobs.contains("synapse_full")),
                                          rx.button("Count tracks", on_click=UI.start_job("synapse_count"), disabled=UI.pending_jobs.contains("synapse_count") | UI.running_jobs.contains("synapse_count"), variant="outline"),
                                          rx.button("View details", on_click=UI.select_job("synapse_full"), variant="outline"), class_name="synapse-admin-actions"),
                                rx.text(UI.job_errors.get("synapse_full", ""), role="status"),
                                rx.text(UI.job_errors.get("synapse_count", ""), role="status"), class_name="synapse-admin-main"),
                         rx.box(rx.html(synapse_network_svg()),
                                class_name=rx.cond(UI.running_jobs.contains("synapse_full") | UI.running_jobs.contains("synapse_limited"), "synapse-neuron is-active", "synapse-neuron"),
                                aria_hidden="true"), class_name="synapse-admin-layout"),
                     class_name="panel synapse-admin-panel"), id="synapse"),
               id="library-tools", class_name="admin-section"),
        rx.box(rx.heading("Data transfers", as_="h2", size="5"),
               panel("Import Apple Music / iTunes history", rx.text("Import an XML library export into MusicMind. Existing ratings are preserved and the higher play count is retained."),
                     rx.text("Known last-played dates can contribute to timelines; the export does not contain the complete sequence of historical plays."),
                     rx.upload(rx.text("Choose or drop an XML file · maximum 50 MiB"),
                               rx.text("In Apple Music or iTunes, choose File → Library → Export Library and select the XML file. Aggregate counts are not distributed across invented dates."), id="itunes-library", class_name="itunes-dropzone", multiple=False, max_files=1, max_size=50 * 1024 * 1024, accept={"text/xml": [".xml"], "application/xml": [".xml"]}, disabled=UI.itunes_importing),
                     rx.foreach(rx.selected_files("itunes-library"), lambda name: rx.text(name)),
                     rx.button("Import history", loading=UI.itunes_importing, disabled=(rx.selected_files("itunes-library").length() == 0) | UI.itunes_importing, on_click=UI.import_itunes(rx.upload_files(upload_id="itunes-library"))),
                     rx.text(UI.itunes_result, role="status")),
               panel("Sync star ratings with Plex", rx.text("Existing Plex ratings take priority and update MusicMind. MusicMind ratings fill only unrated tracks in Plex."),
                     rx.button("Sync star ratings", on_click=UI.sync_musicmind_ratings, loading=UI.ratings_syncing, disabled=UI.ratings_syncing), rx.text(UI.ratings_result, role="status")),
               id="data-transfers", class_name="admin-section"),
        rx.box(rx.heading("Advanced tasks", as_="h2", size="5"),
               rx.box(*[rx.el.details(rx.el.summary(rx.hstack(rx.box(rx.heading(group, size="4", class_name="job-group-title"), rx.text(description, class_name="job-group-description"), rx.text(f"{len(items)} tasks", class_name="job-group-description")), rx.icon("chevron-down", size=18), justify="between", class_name="job-group-header")),
                          rx.box(rx.text("Runs the tasks below in order."),
                                 rx.button("Run all tasks in this group", on_click=UI.start_job(f"group_{group.lower()}"), disabled=UI.running_jobs.contains(f"group_{group.lower()}") | UI.running_jobs.contains("fullsync") | UI.pending_jobs.contains(f"group_{group.lower()}")),
                                 rx.text(UI.job_errors.get(f"group_{group.lower()}", ""), role="status"),
                                 *[job_entry(name, label, detail, group) for name, label, detail in items], class_name="job-list"), class_name="job-group") for group, description, items in JOB_GROUPS if group != "Library"], class_name="job-groups"),
               id="advanced-tasks", class_name="admin-section"),
        job_status_dialog(), class_name="admin-workspace"))
