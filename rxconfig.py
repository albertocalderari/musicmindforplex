"""Reflex configuration for the MusicMind interface."""

import reflex as rx
from reflex_components_radix.themes.base import Theme

from musicmind_ui.state import UI


class MusicMindTheme(Theme):
    """Pass the selected appearance to Radix, including its portal context."""

    def _render(self, props=None):
        # Reflex normally delegates appearance to its independent light/dark picker.
        return super()._render(props).add_props(appearance=self.appearance)


config = rx.Config(
    app_name="musicmind_ui",
    frontend_port=8787,
    backend_port=8787,
    disable_plugins=[rx.plugins.SitemapPlugin],
    plugins=[rx.plugins.RadixThemesPlugin(
        theme=MusicMindTheme.create(
            appearance=rx.cond(UI.theme == "midnight", "dark", "light"),
            accent_color=rx.match(UI.theme, ("parchment", "brown"), ("ocean", "blue"),
                                  ("forest", "green"), ("midnight", "brown"), "blue"),
            gray_color=rx.match(UI.theme, ("parchment", "sand"), ("midnight", "sand"), "slate"),
            radius="large",
        )
    )],
)
