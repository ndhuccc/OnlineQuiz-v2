import pytest
from rest_framework.test import APIClient

from quiz.models import Answer, QuizSession
from quiz.services.import_json import import_question_bank
from quiz.services.schemas import ImportPayload, ImportQuestionItem
from quiz.services.session_fsm import create_session, join_session, open_review, set_phase, start_session
from quiz.services.stats import question_stats_payload, session_summary_payload
from quiz.services.answers import submit_answer


@pytest.fixture
def session_with_answers(db):
    payload = ImportPayload(
        name="統計題庫",
        questions=[
            ImportQuestionItem(
                node="N1",
                format="Single Choice",
                question="Q1",
                options=["A. a", "B. b"],
                correct_answer="A",
            ),
            ImportQuestionItem(
                node="N2",
                format="Single Choice",
                question="Q2",
                options=["A. x", "B. y"],
                correct_answer="B",
            ),
        ],
    )
    bank_id = import_question_bank(payload).bank_id
    session = create_session(bank_id)
    p1 = join_session(session.join_code, "S1", "甲")
    p2 = join_session(session.join_code, "S2", "乙")
    start_session(session)
    session.refresh_from_db()
    set_phase(session, QuizSession.Phase.OPTIONS, timer_seconds=60)
    q = session.current_question()
    opt_a = q.options.get(letter="A")
    submit_answer(participant=p1, question=q, selected_option_ids=[opt_a.id])
    submit_answer(participant=p2, question=q, selected_option_ids=[])
    session.refresh_from_db()
    set_phase(session, QuizSession.Phase.CLOSED)
    return session, p1, p2


@pytest.mark.django_db
def test_question_stats_payload(session_with_answers):
    session, _, _ = session_with_answers
    q = session.current_question()
    stats = question_stats_payload(session, q)
    assert stats["pie"]["counts"][0] == 1  # full
    assert stats["pie"]["counts"][2] == 1  # zero
    assert stats["answer_rate"] == 0.5


@pytest.mark.django_db
def test_session_summary(session_with_answers):
    session, _, _ = session_with_answers
    summary = session_summary_payload(session)
    assert len(summary["question_rates"]) == 2
    assert summary["participant_count"] == 2


@pytest.mark.django_db
def test_open_review_and_student_api(session_with_answers):
    session, p1, _ = session_with_answers
    session.status = QuizSession.Status.SUMMARY
    session.save()
    open_review(session)

    api = APIClient()
    res = api.get(
        "/api/participants/me/review/",
        HTTP_AUTHORIZATION=f"Bearer {p1.client_token}",
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["questions"]) == 2
    assert "correct_answer" in data["questions"][0]
