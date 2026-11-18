"""Reflex configuration for the MusicMind interface."""

import reflex as rx


config = rx.Config(
    app_name="musicmind_ui",
    frontend_port=8787,
    backend_port=8787,
    disable_plugins=[rx.plugins.SitemapPlugin],
    plugins=[rx.plugins.RadixThemesPlugin(
        theme=rx.theme(appearance="light", accent_color="brown",
                       gray_color="sand", radius="large")
    )],
)
