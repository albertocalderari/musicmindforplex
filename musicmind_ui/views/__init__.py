"""MusicMind Reflex pages, grouped by feature."""

from musicmind_ui.job_definitions import JOB_GROUPS, JOB_LABELS
from .admin import admin_page
from .components import (
    BUCKETS,
    filter_input,
    filter_select,
    nav,
    panel,
    shell,
    theme_selector,
    track_row,
)
from .home import home, home_art, home_stat, home_visual_gallery
from .stats import stats_page
from .tools import audit_page, gaps_page, guide_page, logs_page, query_page, tests_page
