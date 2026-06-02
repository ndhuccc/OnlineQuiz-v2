"""Tests that session creation via the API persists the chosen mode.

Bug regression: POST /api/sessions/ used to ignore the `mode` field and
always create AUTO sessions, leaving teachers no way to pick the manual
(評量講解) flow.
"""
import pytest
from rest_framework.test import APIClient

from quiz.services.import_json import import_question_bank
from quiz.services.schemas import ImportPayload, ImportQuestionItem
from quiz.services.session_fsm import create_session


@pytest.fixture
def bank(db):
    payload = ImportPayload(
        name="模式測試題庫",
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
    return import_question_bank(payload).bank_id


@pytest.mark.django_db
def test_session_create_with_manual_mode_persists(bank):
    api = APIClient()
    res = api.post("/api/sessions/", {"bank_id": bank, "mode": "manual"}, format="json")
    assert res.status_code == 201, res.content
    body = res.json()
    assert body["mode"] == "manual"
    assert body["join_code"]
    assert body["host_token"]


@pytest.mark.django_db
def test_session_create_with_auto_mode_persists(bank):
    api = APIClient()
    res = api.post("/api/sessions/", {"bank_id": bank, "mode": "auto"}, format="json")
    assert res.status_code == 201, res.content
    assert res.json()["mode"] == "auto"


@pytest.mark.django_db
def test_session_create_defaults_to_auto_when_omitted(bank):
    api = APIClient()
    res = api.post("/api/sessions/", {"bank_id": bank}, format="json")
    assert res.status_code == 201, res.content
    assert res.json()["mode"] == "auto"


@pytest.mark.django_db
def test_session_create_rejects_invalid_mode(bank):
    api = APIClient()
    res = api.post(
        "/api/sessions/", {"bank_id": bank, "mode": "warp_speed"}, format="json"
    )
    assert res.status_code == 400


@pytest.mark.django_db
def test_manual_mode_start_stays_in_stem(bank):
    """Regression for the bug that prompted this fix: even when mode was
    manual, the start_session() path used to always open OPTIONS.

    Verified by going through the full HTTP API so the integration stays
    honest.
    """
    api = APIClient()
    res = api.post("/api/sessions/", {"bank_id": bank, "mode": "manual"}, format="json")
    session_id = res.json()["id"]
    host_token = res.json()["host_token"]

    detail = api.get(
        f"/api/sessions/{session_id}/",
        HTTP_AUTHORIZATION=f"Bearer {host_token}",
    ).json()
    # Before start, session is in LOBBY with no phase yet.
    assert detail["status"] == "lobby"

    # Start the session.
    api.post(
        f"/api/sessions/{session_id}/start/",
        HTTP_AUTHORIZATION=f"Bearer {host_token}",
    )

    after_start = api.get(
        f"/api/sessions/{session_id}/",
        HTTP_AUTHORIZATION=f"Bearer {host_token}",
    ).json()
    # MANUAL mode: start_session() must NOT auto-open OPTIONS.
    assert after_start["current_phase"] == "stem", after_start
