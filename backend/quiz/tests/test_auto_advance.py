"""Tests for server-side auto-advance scheduler in AUTO mode."""
import time

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from quiz.models import Answer, QuizSession
from quiz.services.import_json import import_question_bank
from quiz.services.schemas import ImportPayload, ImportQuestionItem
from quiz.services.session_fsm import (
    advance_scheduler,
    create_session,
    join_session,
    next_question,
    set_phase,
    start_session,
)


@pytest.fixture
def two_q_bank(db):
    payload = ImportPayload(
        name="two Q bank",
        questions=[
            ImportQuestionItem(
                node="N1",
                format="Single Choice",
                question="Q1?",
                options=["A. a", "B. b"],
                correct_answer="A",
            ),
            ImportQuestionItem(
                node="N2",
                format="Single Choice",
                question="Q2?",
                options=["A. x", "B. y"],
                correct_answer="B",
            ),
        ],
    )
    result = import_question_bank(payload)
    return result.bank_id


@pytest.fixture(autouse=True)
def _clean_scheduler():
    """Ensure no pending advances bleed between tests."""
    advance_scheduler.cancel_all()
    yield
    advance_scheduler.cancel_all()


@pytest.mark.django_db(transaction=True)
def test_auto_mode_advances_after_close(two_q_bank):
    """In auto mode, after a question closes, server auto-advances after grace."""
    import quiz.services.session_fsm as fsm

    original_grace = fsm.AUTO_ADVANCE_GRACE_SECONDS
    fsm.AUTO_ADVANCE_GRACE_SECONDS = 0.3  # speed up for test
    try:
        session = create_session(two_q_bank, mode=QuizSession.Mode.AUTO)
        join_session(session.join_code, "S001", "甲")
        start_session(session)
        assert session.current_question_index == 0
        assert session.current_phase == QuizSession.Phase.OPTIONS

        # Close Q1
        set_phase(session, QuizSession.Phase.CLOSED)
        assert session.current_phase == QuizSession.Phase.CLOSED
        # Auto-advance should be scheduled
        assert advance_scheduler.is_pending(session.id)

        # Wait fixed time for the scheduler thread to fire
        time.sleep(1.5)

        session.refresh_from_db()
        assert session.current_question_index == 1, "expected auto-advance to Q2"
        assert session.current_phase == QuizSession.Phase.OPTIONS
        assert not advance_scheduler.is_pending(session.id)
    finally:
        fsm.AUTO_ADVANCE_GRACE_SECONDS = original_grace


@pytest.mark.django_db(transaction=True)
def test_manual_mode_does_not_auto_advance(two_q_bank):
    """In manual mode, after a question closes, the server does NOT auto-advance."""
    session = create_session(two_q_bank, mode=QuizSession.Mode.MANUAL)
    join_session(session.join_code, "S001", "甲")
    start_session(session)
    assert session.current_question_index == 0

    # Close Q1
    set_phase(session, QuizSession.Phase.CLOSED)
    assert session.current_phase == QuizSession.Phase.CLOSED

    # No auto-advance should be scheduled
    assert not advance_scheduler.is_pending(session.id)

    # Wait a bit and verify still in closed/Q1
    time.sleep(0.5)
    session.refresh_from_db()
    assert session.current_question_index == 0
    assert session.current_phase == QuizSession.Phase.CLOSED


@pytest.mark.django_db(transaction=True)
def test_manual_next_cancels_pending_advance(two_q_bank):
    """If a teacher manually calls /next/ while auto-advance is pending, the
    scheduled callback should be cancelled (no double-advance).
    """
    import quiz.services.session_fsm as fsm

    original_grace = fsm.AUTO_ADVANCE_GRACE_SECONDS
    fsm.AUTO_ADVANCE_GRACE_SECONDS = 5.0  # long enough to manually intervene
    try:
        session = create_session(two_q_bank, mode=QuizSession.Mode.AUTO)
        join_session(session.join_code, "S001", "甲")
        start_session(session)

        # Close Q1, auto-advance is now scheduled
        set_phase(session, QuizSession.Phase.CLOSED)
        assert advance_scheduler.is_pending(session.id)

        # Teacher manually advances
        next_question(session)
        # Auto-advance should have been cancelled
        assert not advance_scheduler.is_pending(session.id)
        assert session.current_question_index == 1
    finally:
        fsm.AUTO_ADVANCE_GRACE_SECONDS = original_grace


@pytest.mark.django_db(transaction=True)
def test_last_question_auto_advances_to_review(two_q_bank):
    """After the last question closes in auto mode, server transitions to review."""
    import quiz.services.session_fsm as fsm

    original_grace = fsm.AUTO_ADVANCE_GRACE_SECONDS
    fsm.AUTO_ADVANCE_GRACE_SECONDS = 0.3
    try:
        session = create_session(two_q_bank, mode=QuizSession.Mode.AUTO)
        join_session(session.join_code, "S001", "甲")
        start_session(session)
        # Advance to Q2
        set_phase(session, QuizSession.Phase.CLOSED)
        next_question(session)
        assert session.current_question_index == 1

        # Close Q2 → auto-advance will go to review
        set_phase(session, QuizSession.Phase.CLOSED)
        assert advance_scheduler.is_pending(session.id)

        time.sleep(1.5)

        session.refresh_from_db()
        assert session.status == QuizSession.Status.REVIEW
    finally:
        fsm.AUTO_ADVANCE_GRACE_SECONDS = original_grace
