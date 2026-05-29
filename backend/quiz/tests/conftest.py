import pytest

from quiz.services.session_fsm import invalidate_pending_schedules


@pytest.fixture(autouse=True)
def _clear_timers():
    invalidate_pending_schedules()
    yield
    invalidate_pending_schedules()
