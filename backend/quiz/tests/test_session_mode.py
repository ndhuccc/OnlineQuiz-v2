"""Tests for the session.mode field (auto vs manual)."""
import pytest
from rest_framework.test import APIClient

from quiz.models import QuizSession
from quiz.services.import_json import import_question_bank
from quiz.services.schemas import ImportPayload, ImportQuestionItem
from quiz.services.session_fsm import create_session


@pytest.fixture
def bank(db):
    payload = ImportPayload(
        name="mode bank",
        questions=[
            ImportQuestionItem(
                node="N1",
                format="Single Choice",
                question="Q1?",
                options=["A. a", "B. b"],
                correct_answer="A",
            ),
        ],
    )
    result = import_question_bank(payload)
    return result.bank_id


@pytest.mark.django_db
def test_new_session_defaults_to_auto_mode(bank):
    """Sessions created without specifying mode default to auto."""
    session = create_session(bank)
    assert session.mode == QuizSession.Mode.AUTO


@pytest.mark.django_db
def test_create_session_with_manual_mode(bank):
    """Sessions can be created with manual mode for the future explanation feature."""
    session = create_session(bank, mode=QuizSession.Mode.MANUAL)
    assert session.mode == QuizSession.Mode.MANUAL


@pytest.mark.django_db
def test_state_payload_includes_mode(bank):
    """The session_state payload includes the mode so the frontend can branch."""
    session = create_session(bank, mode=QuizSession.Mode.MANUAL)
    from quiz.services.session_fsm import session_state_payload

    payload = session_state_payload(session)
    assert payload["mode"] == "manual"
