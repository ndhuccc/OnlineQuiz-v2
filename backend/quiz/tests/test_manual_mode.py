"""Tests for MANUAL mode (評量講解) per-question result endpoint."""
import pytest
from rest_framework.test import APIClient

from quiz.models import QuizSession
from quiz.services.import_json import import_question_bank
from quiz.services.schemas import ImportPayload, ImportQuestionItem
from quiz.services.session_fsm import (
    create_session,
    join_session,
    next_question,
    set_phase,
    start_session,
)


@pytest.fixture
def bank(db):
    payload = ImportPayload(
        name="manual mode bank",
        questions=[
            ImportQuestionItem(
                node="N1",
                format="Single Choice",
                question="Q1 stem",
                options=["A. alpha", "B. beta"],
                correct_answer="A",
            ),
            ImportQuestionItem(
                node="N2",
                format="Multiple Choice",
                question="Q2 stem",
                options=["A. p", "B. q", "C. r"],
                correct_answer="AC",
            ),
        ],
    )
    result = import_question_bank(payload)
    return result.bank_id


@pytest.fixture
def manual_session(bank):
    session = create_session(bank, mode=QuizSession.Mode.MANUAL)
    join_session(session.join_code, "S001", "甲")
    return session


@pytest.mark.django_db(transaction=True)
def test_manual_start_session_keeps_stem_phase(manual_session):
    """MANUAL mode: after start, phase should be STEM (teacher must
    explicitly click 'Open Options')."""
    start_session(manual_session)
    manual_session.refresh_from_db()
    assert manual_session.current_phase == QuizSession.Phase.STEM
    assert manual_session.status == QuizSession.Status.RUNNING


@pytest.mark.django_db(transaction=True)
def test_manual_session_state_payload_includes_mode(manual_session):
    """Smoke test: mode is in state payload."""
    from quiz.services.session_fsm import session_state_payload

    payload = session_state_payload(manual_session)
    assert payload["mode"] == "manual"


@pytest.mark.django_db(transaction=True)
def test_question_result_rejected_during_options_phase(manual_session):
    """In OPTIONS phase, students cannot see the correct answer yet."""
    start_session(manual_session)
    set_phase(manual_session, QuizSession.Phase.OPTIONS, timer_seconds=60)

    api = APIClient()
    res = api.post(
        "/api/sessions/join/",
        {
            "join_code": manual_session.join_code,
            "student_no": "S001",
            "display_name": "甲",
        },
        format="json",
    )
    # Rejoin to get a fresh client_token
    token = res.json()["client_token"]

    res = api.get(
        "/api/participants/me/question_result/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 403
    assert "尚未結束" in res.json()["detail"]


@pytest.mark.django_db(transaction=True)
def test_question_result_rejected_in_stem_phase(manual_session):
    """In STEM phase (before teacher opens options), 403 too."""
    start_session(manual_session)
    manual_session.refresh_from_db()
    assert manual_session.current_phase == QuizSession.Phase.STEM

    res = api_post_join(manual_session, "S001", "甲")
    token = res["client_token"]

    api = APIClient()
    res = api.get(
        "/api/participants/me/question_result/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 403


@pytest.mark.django_db(transaction=True)
def test_question_result_available_after_closed(manual_session):
    """After teacher closes the question, student can see correct answer + score."""
    start_session(manual_session)
    set_phase(manual_session, QuizSession.Phase.OPTIONS, timer_seconds=60)

    res = api_post_join(manual_session, "S001", "甲")
    token = res["client_token"]

    # Fetch options and submit the correct answer
    opts = api_post_options(APIClient(), token)
    correct_id = next(o["id"] for o in opts["options"] if o["label_text"] == "alpha")
    sub = APIClient().post(
        "/api/participants/me/answers/",
        {"option_ids": [correct_id]},
        HTTP_AUTHORIZATION=f"Bearer {token}",
        format="json",
    )
    assert sub.status_code == 201
    assert sub.json()["answer"]["is_full_score"] is True  # immediate grading ✓

    # Now teacher closes the question
    set_phase(manual_session, QuizSession.Phase.CLOSED)

    api = APIClient()
    res = api.get(
        "/api/participants/me/question_result/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["question"]["question_index"] == 0
    assert body["question"]["correct_answer"] == "A"
    assert body["question"]["your_answer"] == "A"
    assert body["question"]["is_full_score"] is True
    assert float(body["question"]["score"]) == 1.0


@pytest.mark.django_db(transaction=True)
def test_question_result_shows_wrong_answer(manual_session):
    """Student who picked wrong option sees their wrong answer vs correct."""
    start_session(manual_session)
    set_phase(manual_session, QuizSession.Phase.OPTIONS, timer_seconds=60)

    res = api_post_join(manual_session, "S001", "甲")
    token = res["client_token"]

    opts = api_post_options(APIClient(), token)
    wrong_id = next(o["id"] for o in opts["options"] if o["label_text"] == "beta")
    sub = APIClient().post(
        "/api/participants/me/answers/",
        {"option_ids": [wrong_id]},
        HTTP_AUTHORIZATION=f"Bearer {token}",
        format="json",
    )
    assert sub.json()["answer"]["is_full_score"] is False  # 立即評分

    set_phase(manual_session, QuizSession.Phase.CLOSED)

    api = APIClient()
    res = api.get(
        "/api/participants/me/question_result/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 200
    body = res.json()
    assert body["question"]["correct_answer"] == "A"
    assert body["question"]["your_answer"] == "B"
    assert body["question"]["is_full_score"] is False
    assert float(body["question"]["score"]) == 0.0


@pytest.mark.django_db(transaction=True)
def test_manual_advance_to_next_keeps_stem_phase(manual_session):
    """MANUAL mode: after teacher clicks next, the new question is in STEM
    (teacher must click 'Open Options' for each new question).
    """
    start_session(manual_session)
    set_phase(manual_session, QuizSession.Phase.OPTIONS, timer_seconds=60)
    set_phase(manual_session, QuizSession.Phase.CLOSED)

    next_question(manual_session)
    manual_session.refresh_from_db()
    assert manual_session.current_question_index == 1
    assert manual_session.current_phase == QuizSession.Phase.STEM
    assert manual_session.status == QuizSession.Status.RUNNING


@pytest.mark.django_db(transaction=True)
def test_question_result_includes_explanation_text(manual_session, bank):
    """Smoke test: explanation_text is present in the payload."""
    # The fixture's question doesn't have explanation_text. Add one.
    from quiz.models import Question

    q = Question.objects.filter(bank__id=bank).first()
    q.explanation_text = "因為 alpha 是對的選項"
    q.save()

    start_session(manual_session)
    set_phase(manual_session, QuizSession.Phase.OPTIONS, timer_seconds=60)
    set_phase(manual_session, QuizSession.Phase.CLOSED)

    res = api_post_join(manual_session, "S001", "甲")
    token = res["client_token"]
    api = APIClient()
    res = api.get(
        "/api/participants/me/question_result/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )
    assert res.status_code == 200
    body = res.json()
    assert body["question"]["explanation_text"] == "因為 alpha 是對的選項"


# ---- helpers ----


def api_post_join(session, student_no, display_name):
    api = APIClient()
    res = api.post(
        "/api/sessions/join/",
        {
            "join_code": session.join_code,
            "student_no": student_no,
            "display_name": display_name,
        },
        format="json",
    )
    return res.json()


def api_post_options(api, token):
    return api.post(
        "/api/participants/me/options/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    ).json()
