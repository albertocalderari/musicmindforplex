"""Controlled checks for admin lifecycle presentation and preview invalidation."""
import pytest

from musicmind_ui.state import UI


@pytest.mark.parametrize(("result", "expected"), [
    ({"running": True}, "Running"),
    ({"running": False, "exit_code": 0}, "Completed"),
    ({"running": False, "exit_code": 1}, "Failed"),
    ({"running": False, "exit_code": 143, "stopped": True}, "Stopped"),
    ({"running": False, "exit_code": None}, "No recorded result / interrupted"),
])
def test_job_result_presentation(result, expected):
    assert UI(_reflex_internal_init=True)._job_result_state(result) == expected


def test_changing_album_invalidates_preview():
    state = UI(_reflex_internal_init=True)
    state.resync_preview_ready = True
    state.resync_preview_requested = True
    state.set_resync_album("Another album")
    assert not state.resync_preview_ready
    assert not state.resync_preview_requested
