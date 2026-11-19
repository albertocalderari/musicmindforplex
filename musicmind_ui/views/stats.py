"""Collection statistics page and chart components."""

import reflex as rx
from musicmind_ui.state import UI
from .components import panel, shell


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


