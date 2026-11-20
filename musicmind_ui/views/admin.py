"""Admin and background job pages."""

from random import Random

import reflex as rx
from musicmind_ui.job_definitions import JOB_GROUPS, JOB_LABELS
from musicmind_ui.state import LASTFM_KEY, UI
from .components import panel, shell


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


