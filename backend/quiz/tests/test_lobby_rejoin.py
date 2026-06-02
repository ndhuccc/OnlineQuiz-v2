"""Tests for join_session edge cases — lobby rejoin and duplicate prevention."""
import pytest
from rest_framework.test import APIClient

from quiz.services.import_json import import_question_bank
from quiz.services.schemas import ImportPayload, ImportQuestionItem
from quiz.services.session_fsm import create_session, join_session, start_session


@pytest.fixture
def bank(db):
    payload = ImportPayload(
        name="lobby rejoin bank",
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
def test_lobby_rejoin_after_lost_token_succeeds(bank):
    """After a student loses their client_token (closed tab, cleared localStorage),
    re-entering the join form with the same student_no should succeed in lobby.
    This used to fail with '此學號已加入本場次' before the rescue removal fixup.
    """
    session = create_session(bank)
    p1 = join_session(session.join_code, "S001", "甲")
    original_token = p1.client_token

    # Student loses token (e.g. closed browser, localStorage gone)
    # and re-enters with the same student_no
    p2 = join_session(session.join_code, "S001", "甲")
    assert p2.id == p1.id
    assert p2.client_token != original_token
    assert p2.client_token != ""


@pytest.mark.django_db
def test_lobby_rejoin_via_api_returns_new_token(bank):
    """End-to-end: two POST /api/sessions/join/ with the same student_no
    in lobby should both succeed and the second one returns a fresh token.
    """
    api = APIClient()
    body = {
        "join_code": "",
        "student_no": "S001",
        "display_name": "甲",
    }
    # Get the actual join_code from the bank fixture
    session = create_session(bank)
    body["join_code"] = session.join_code

    first = api.post("/api/sessions/join/", body, format="json")
    assert first.status_code == 201
    first_token = first.json()["client_token"]

    # Simulate lost client_token: try to rejoin
    second = api.post("/api/sessions/join/", body, format="json")
    assert second.status_code == 201, second.content
    second_token = second.json()["client_token"]
    assert second_token != first_token

    # participant.id should be the same
    assert first.json()["participant"]["id"] == second.json()["participant"]["id"]


@pytest.mark.django_db
def test_lobby_rejoin_does_not_change_joined_at(bank):
    """Rejoin in lobby should preserve joined_at; not reset the clock."""
    session = create_session(bank)
    p1 = join_session(session.join_code, "S001", "甲")
    original_joined = p1.joined_at

    p2 = join_session(session.join_code, "S001", "甲")
    assert p2.joined_at == original_joined


@pytest.mark.django_db
def test_student_cannot_join_twice_in_lobby_with_different_info(bank):
    """Even in lobby, the participant record is unique per (session, student_no).
    Two DIFFERENT student_nos should both succeed; same student_no rejoin is OK
    (covered above). This test just confirms normal new-join still works.
    """
    session = create_session(bank)
    a = join_session(session.join_code, "S001", "甲")
    b = join_session(session.join_code, "S002", "乙")
    assert a.id != b.id
    assert a.student_no == "S001"
    assert b.student_no == "S002"


@pytest.mark.django_db
def test_unknown_student_cannot_join_after_quiz_starts(bank):
    """Brand new student_nos are still rejected mid-quiz — only rejoin works."""
    session = create_session(bank)
    join_session(session.join_code, "S001", "甲")
    start_session(session)

    import pytest

    with pytest.raises(Exception) as exc_info:
        join_session(session.join_code, "S999", "新生")
    assert "無法新加入" in str(exc_info.value)


@pytest.mark.django_db
def test_existing_student_can_rejoin_after_quiz_starts(bank):
    """Rejoin mid-quiz still works (covered before, regression check)."""
    session = create_session(bank)
    p1 = join_session(session.join_code, "S001", "甲")
    start_session(session)

    p2 = join_session(session.join_code, "S001", "甲")
    assert p2.id == p1.id
    assert p2.client_token != p1.client_token
    assert p2.start_question_index == session.current_question_index
