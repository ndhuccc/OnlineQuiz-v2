"""Tests for explicit multi-tab detection (X-Tab-Id + 409 Conflict)."""
import pytest
from rest_framework.test import APIClient

from quiz.services.import_json import import_question_bank
from quiz.services.schemas import ImportPayload, ImportQuestionItem
from quiz.services.session_fsm import create_session, join_session, start_session


@pytest.fixture
def bank(db):
    payload = ImportPayload(
        name="multi-tab bank",
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


@pytest.fixture
def running_session_with_participant(bank):
    """A session that's already running with student S001 already joined."""
    session = create_session(bank)
    join_session(session.join_code, "S001", "甲")
    start_session(session)
    session.refresh_from_db()
    return session


@pytest.mark.django_db
def test_tab_takeover_returns_409(running_session_with_participant):
    """When student A rejoins with a new tab_id, A's old tab gets 409
    (provided A sends X-Participant-Id so the server can find the stale token)."""
    api = APIClient()
    join = api.post(
        "/api/sessions/join/",
        {
            "join_code": running_session_with_participant.join_code,
            "student_no": "S001",
            "display_name": "甲",
            "tab_id": "tab-A",
        },
        format="json",
    )
    assert join.status_code == 201
    body_a = join.json()
    token_a = body_a["client_token"]
    pid_a = body_a["participant"]["id"]

    # Tab B rejoins with a different tab_id
    rejoin = api.post(
        "/api/sessions/join/",
        {
            "join_code": running_session_with_participant.join_code,
            "student_no": "S001",
            "display_name": "甲",
            "tab_id": "tab-B",
        },
        format="json",
    )
    assert rejoin.status_code == 201
    token_b = rejoin.json()["client_token"]
    assert token_b != token_a

    # Tab A polls with the OLD token and tab-A id (and X-Participant-Id for fallback lookup)
    res = api.get(
        "/api/participants/me/",
        HTTP_AUTHORIZATION=f"Bearer {token_a}",
        HTTP_X_TAB_ID="tab-A",
        HTTP_X_PARTICIPANT_ID=str(pid_a),
    )
    assert res.status_code == 409, res.content
    err = res.json()
    assert err.get("code") == "tab_taken_over"

    # Tab B with the NEW token and tab-B id → 200 OK
    res_b = api.get(
        "/api/participants/me/",
        HTTP_AUTHORIZATION=f"Bearer {token_b}",
        HTTP_X_TAB_ID="tab-B",
    )
    assert res_b.status_code == 200


@pytest.mark.django_db
def test_stale_token_without_participant_id_returns_auth_failure(running_session_with_participant):
    """If a tab holds an old token but doesn't send X-Participant-Id,
    the server can't tell takeover from a regular auth failure, so it
    returns 401/403 (DRF default for AuthenticationFailed).
    The frontend should always send X-Participant-Id when it has a client_token.
    """
    api = APIClient()
    join = api.post(
        "/api/sessions/join/",
        {
            "join_code": running_session_with_participant.join_code,
            "student_no": "S001",
            "display_name": "甲",
            "tab_id": "tab-A",
        },
        format="json",
    ).json()

    # Tab B rejoins → token invalidated
    api.post(
        "/api/sessions/join/",
        {
            "join_code": running_session_with_participant.join_code,
            "student_no": "S001",
            "display_name": "甲",
            "tab_id": "tab-B",
        },
        format="json",
    )

    res = api.get(
        "/api/participants/me/",
        HTTP_AUTHORIZATION=f"Bearer {join['client_token']}",
        HTTP_X_TAB_ID="tab-A",
        # no X-Participant-Id
    )
    assert res.status_code in (401, 403)


@pytest.mark.django_db
def test_valid_token_with_matching_tab_returns_200(running_session_with_participant):
    """Sanity check: the happy path still works."""
    api = APIClient()
    join = api.post(
        "/api/sessions/join/",
        {
            "join_code": running_session_with_participant.join_code,
            "student_no": "S001",
            "display_name": "甲",
            "tab_id": "tab-A",
        },
        format="json",
    ).json()

    res = api.get(
        "/api/participants/me/",
        HTTP_AUTHORIZATION=f"Bearer {join['client_token']}",
        HTTP_X_TAB_ID="tab-A",
        HTTP_X_PARTICIPANT_ID=str(join["participant"]["id"]),
    )
    assert res.status_code == 200
