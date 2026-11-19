"""Shared navigation, layout, and playlist components."""

import reflex as rx
from musicmind_ui.state import LASTFM_KEY, UI


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


