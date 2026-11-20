"""The Collection: source-labelled statistics with accessible data alternatives."""
import reflex as rx
from reflex_components_core.base.error_boundary import ErrorBoundary
from musicmind_ui.state import UI
from .components import shell


def chart_frame(chart):
    # A chart failure must not remove the independently rendered data table.
    return ErrorBoundary.create(
        rx.box(chart, aria_hidden=True),
        fallback_render=rx.Var.create(rx.text(
            "Chart unavailable. Exact values remain available in View data below.",
            role="status", class_name="collection-note")))


def tooltip():
    return rx.recharts.graphing_tooltip(
        is_animation_active=False,
        custom_attrs={"formatter": rx.Var(
            _js_expr="(value, name) => [Number(value).toLocaleString(), name]")})


def empty(message: str, action: str = "Manage library and enrichment"):
    return rx.box(rx.text(message), rx.link(action, href="/admin"), class_name="collection-empty")


def data_table(rows, label: str, *, timeline=False):
    return rx.el.table(
        rx.el.caption(label),
        rx.el.thead(rx.el.tr(rx.el.th("Period" if timeline else "Category", scope="col"),
                              rx.el.th("Recorded plays" if timeline else "Artists", scope="col"))),
        rx.el.tbody(rx.foreach(rows, lambda row: rx.el.tr(
            rx.el.th(row["label"] if timeline else row["name"], scope="row"),
            rx.el.td(row["display"] if timeline else row["count"])))),
        class_name="collection-table")


def disclosure(title: str, *children):
    return rx.el.details(rx.el.summary(title), *children, class_name="collection-disclosure")


def heading(title: str, caption, control=None):
    return rx.box(rx.box(rx.heading(title, as_="h2", class_name="chart-title"),
                         rx.text(caption, class_name="chart-caption")),
                  control if control is not None else rx.fragment(), class_name="collection-panel-heading")


def ranked_list(kind: str, title: str, caption):
    value = {"artist": UI.artist_limit, "genre": UI.genre_limit, "country": UI.country_limit}[kind]
    label = {"artist": "Artist", "genre": "Genre", "country": "Country"}[kind] + " results"
    rows = UI.stats_visible[kind]
    return rx.el.section(
        heading(title, caption,
                rx.box(rx.el.label(label, html_for=f"{kind}-limit"),
                       rx.select(["10", "25", "50", "100"], value=value, id=f"{kind}-limit",
                                 aria_label=label, on_change=lambda v: UI.set_stats_limit(kind, v)),
                       class_name="collection-result-control")),
        rx.cond(UI.stats_rankings[kind].length() > 0,
            rx.fragment(
                rx.el.ol(rx.foreach(rows, lambda row: rx.el.li(
                    rx.text(row["rank"], class_name="collection-rank", aria_hidden=True),
                    rx.box(rx.text(row["name"], class_name="collection-row-name"),
                           rx.box(rx.box(style={"width": row["width"]}),
                                  class_name="collection-row-bar", aria_hidden=True)),
                    rx.text(row["count"], class_name="collection-count"))),
                    start=UI.stats_pages[kind] * 10 + 1, role="list", class_name="collection-ranking"),
                rx.el.nav(
                    rx.button("Previous", on_click=UI.stats_turn_page(kind, -1),
                              disabled=UI.stats_pages[kind] == 0, variant="outline"),
                    rx.text(UI.stats_ranges[kind], aria_live="polite"),
                    rx.button("Next", on_click=UI.stats_turn_page(kind, 1),
                              disabled=(UI.stats_pages[kind] + 1) * 10 >= UI.stats_rankings[kind].length(),
                              variant="outline"),
                    aria_label=f"{title} pages", class_name="collection-pagination")),
            empty("No recorded plays yet." if kind == "artist" else "No metadata available yet.")),
        class_name="collection-chart collection-ranked")


def overview():
    def metric(label, key):
        return rx.box(rx.text(label, class_name="metric-label"),
                      rx.text(UI.stats_display[key], class_name="metric-value"), class_name="metric-card")
    return rx.el.section(
        rx.text("LIBRARY OVERVIEW · PLEX", class_name="section-kicker"),
        rx.box(metric("Tracks", "total_tracks"), metric("Artists", "total_artists"),
               class_name="collection-metrics"),
        rx.text("Instrumental tracks: ", UI.stats_display["total_instrumental"],
                " · Based on available metadata", class_name="collection-note"),
        rx.cond(UI.stats_summary["total_tracks"] == 0, empty("No tracks found.", "Set up or sync your library")),
        class_name="collection-section")


def listening():
    return rx.el.section(
        rx.text("LISTENING · LAST.FM", class_name="section-kicker"),
        rx.box(heading("Your listening over time", "Recorded plays: " + UI.stats_display["total_scrobbles"]),
            rx.cond(UI.listening_rows.length() > 0,
                rx.fragment(
                    chart_frame(rx.recharts.line_chart(
                        rx.recharts.cartesian_grid(stroke="var(--collection-grid)", vertical=False),
                        rx.recharts.x_axis(data_key="label", min_tick_gap=42, tick_line=False,
                                           stroke="var(--muted)"),
                        rx.recharts.y_axis(allow_decimals=False, domain=[0, "auto"], width=55,
                                           stroke="var(--muted)"),
                        tooltip(),
                        rx.recharts.line(data_key="plays", name="Recorded plays", type_="linear",
                                         stroke="var(--collection-listening)", stroke_width=3,
                                         connect_nulls=False, is_animation_active=False, dot=True),
                        data=UI.listening_rows, width="100%", height=280,
                        margin={"top": 12, "right": 16, "bottom": 8, "left": 0})),
                    rx.text("Recorded plays · Gaps mean no recorded data; sync coverage is unknown. Periods use the server’s local time.",
                            class_name="collection-note"),
                    disclosure("View listening data", data_table(UI.listening_rows, "Last.fm recorded listening", timeline=True))),
                empty("No listening history yet.", "Sync Last.fm in Admin")),
            class_name="collection-chart collection-listening"), class_name="collection-section")


def decades():
    return rx.el.section(
        heading("Across the decades", "Current library artists by enriched era; unknown eras excluded"),
        rx.cond(UI.by_era.length() > 0,
            rx.fragment(
                chart_frame(rx.recharts.bar_chart(
                    rx.recharts.cartesian_grid(stroke="var(--collection-grid)", vertical=False),
                    rx.recharts.x_axis(data_key="era", min_tick_gap=24, stroke="var(--muted)"),
                    rx.recharts.y_axis(allow_decimals=False, domain=[0, "auto"], width=45, stroke="var(--muted)"),
                    tooltip(),
                    rx.recharts.bar(data_key="cnt", name="Artists", fill="var(--collection-composition)",
                                    is_animation_active=False, radius=[4, 4, 0, 0]),
                    data=UI.by_era, width="100%", height=280)),
                disclosure("View decade data", data_table(UI.era_rows, "Artists by enriched era"))),
            empty("No era metadata available yet.")), class_name="collection-chart")


def stats_page():
    return shell("The Collection", "Your music, in perspective.",
        rx.el.main(
            rx.el.header(
                rx.box(rx.text("THE COLLECTION", class_name="section-kicker"),
                       rx.heading("Your music, in perspective.", as_="h1", class_name="collection-title"),
                       rx.text("Plex library and Last.fm listening history.", class_name="collection-note")),
                rx.link(rx.icon("download", size=16), "Export library CSV", href="/export-csv",
                        download=True, class_name="collection-export"), class_name="collection-header"),
            rx.box(
                rx.cond(UI.stats_loading, rx.text(rx.cond(UI.stats_loaded, "Refreshing collection…", "Loading collection…"))),
                rx.cond(UI.stats_error != "", rx.box(
                    rx.text(rx.cond(UI.stats_loaded, "Showing previous data. ", ""), UI.stats_error),
                    rx.button("Retry", on_click=UI.stats_load, disabled=UI.stats_loading))),
                role="status", aria_live="polite", class_name="collection-status"),
            rx.cond(UI.stats_loaded,
                rx.fragment(overview(), listening(),
                    rx.el.section(
                        rx.text("IN YOUR LIBRARY", class_name="section-kicker"),
                        rx.box(
                            ranked_list("artist", "Most played artists", "Library track play counts · Plex and imported history"),
                            ranked_list("genre", "Genres", rx.cond(UI.genre_source == "plex",
                                "Tracks by Plex genre field; stored combinations are kept together",
                                "Enriched track-tag assignments; tags may overlap")),
                            ranked_list("country", "Artist origins", "Current library artists by enriched country; unknowns excluded"),
                            decades(), class_name="collection-charts"), class_name="collection-section"),
                    disclosure("Artist metadata", rx.text("Gender categories from enrichment for current library artists. Missing values are unclassified.",
                               class_name="collection-note"),
                               rx.cond(UI.gender_rows.length() > 0,
                                       data_table(UI.gender_rows, "Artist gender metadata"), empty("No artist metadata yet.")))),
                rx.cond(UI.stats_loading, rx.box(
                    *[rx.box(class_name="collection-skeleton") for _ in range(3)],
                    aria_label="Loading collection data", class_name="collection-skeletons"))),
            aria_busy=UI.stats_loading, class_name="collection-page"))
