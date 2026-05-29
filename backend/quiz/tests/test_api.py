import json

import pytest
from rest_framework.test import APIClient

from quiz.services.session_fsm import create_session
from quiz.services.import_json import import_question_bank
from quiz.services.schemas import ImportPayload, ImportQuestionItem


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def sample_bank(db):
    payload = ImportPayload(
        name="API 測試題庫",
        questions=[
            ImportQuestionItem(
                node="單元",
                format="Single Choice",
                question="2+2=?",
                options=["A. 3", "B. 4"],
                correct_answer="B",
            )
        ],
    )
    result = import_question_bank(payload)
    return result.bank_id


@pytest.mark.django_db
def test_health(api):
    res = api.get("/api/health/")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


@pytest.mark.django_db
def test_list_banks(api, sample_bank):
    res = api.get("/api/question-banks/")
    assert res.status_code == 200
    assert len(res.json()) >= 1
    assert res.json()[0]["question_count"] == 1


@pytest.mark.django_db
def test_bank_detail_no_is_correct(api, sample_bank):
    res = api.get(f"/api/question-banks/{sample_bank}/")
    assert res.status_code == 200
    data = res.json()
    assert "questions" in data
    opt = data["questions"][0]["options"][0]
    assert "is_correct" not in opt


@pytest.mark.django_db
def test_import_via_post(api):
    body = {
        "name": "POST 匯入",
        "questions": [
            {
                "node": "N",
                "format": "Multiple Choice",
                "question": "Q",
                "options": ["A. 1", "B. 2", "C. 3"],
                "correct_answer": "AB",
            }
        ],
    }
    res = api.post(
        "/api/question-banks/",
        data=json.dumps(body),
        content_type="application/json",
    )
    assert res.status_code == 201
    assert res.json()["name"] == "POST 匯入"
    assert res.json()["import_report"]["imported_count"] == 1


@pytest.mark.django_db
def test_delete_bank(api, sample_bank):
    res = api.delete(f"/api/question-banks/{sample_bank}/")
    assert res.status_code == 204


@pytest.mark.django_db
def test_delete_bank_with_sessions(api, sample_bank):
    create_session(sample_bank)
    res = api.delete(f"/api/question-banks/{sample_bank}/")
    assert res.status_code == 204
