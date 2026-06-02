import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from quiz.models import Answer, QuizSession
from quiz.services.import_json import import_question_bank
from quiz.services.schemas import ImportPayload, ImportQuestionItem
from quiz.services.session_fsm import create_session, set_phase, start_session
from quiz.services.stats import session_summary_payload


@pytest.fixture
def bank(db):
    payload = ImportPayload(
        name="場次測試題庫",
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
                format="Multiple Choice",
                question="Q2?",
                options=["A. 1", "B. 2", "C. 3"],
                correct_answer="AB",
            ),
        ],
    )
    result = import_question_bank(payload)
    return result.bank_id


@pytest.fixture
def session_setup(bank):
    session = create_session(bank)
    return session


@pytest.mark.django_db
def test_create_and_join(session_setup):
    api = APIClient()
    res = api.post(
        "/api/sessions/join/",
        {
            "join_code": session_setup.join_code,
            "student_no": "S001",
            "display_name": "小明",
        },
        format="json",
    )
    assert res.status_code == 201
    assert "client_token" in res.json()


@pytest.mark.django_db
def test_join_blocked_after_quiz_starts(session_setup):
    api = APIClient()
    body = {
        "join_code": session_setup.join_code,
        "student_no": "S001",
        "display_name": "小明",
    }
    assert api.post("/api/sessions/join/", body, format="json").status_code == 201
    api.post(
        f"/api/sessions/{session_setup.id}/start/",
        HTTP_AUTHORIZATION=f"Bearer {session_setup.host_token}",
    )
    # New student cannot join after quiz starts
    res = api.post(
        "/api/sessions/join/",
        {
            "join_code": session_setup.join_code,
            "student_no": "S002",
            "display_name": "小華",
        },
        format="json",
    )
    assert res.status_code == 400
    assert "無法新加入" in res.json()["detail"]

    # Existing student can rejoin (no rescue needed; rescue mechanism removed)
    dup = api.post("/api/sessions/join/", body, format="json")
    assert dup.status_code == 201


@pytest.mark.django_db
def test_rejoin_unlimited(session_setup):
    """Students can rejoin unlimited times (rescue mechanism removed in 2026-06)."""
    api = APIClient()
    body = {
        "join_code": session_setup.join_code,
        "student_no": "S001",
        "display_name": "小明",
    }
    first = api.post("/api/sessions/join/", body, format="json").json()
    api.post(f"/api/sessions/{session_setup.id}/start/", HTTP_AUTHORIZATION=f"Bearer {session_setup.host_token}")

    # Rejoin once
    rejoin1 = api.post("/api/sessions/join/", body, format="json")
    assert rejoin1.status_code == 201
    assert rejoin1.json()["client_token"] != first["client_token"]

    # Rejoin again — still works (no rejoin_used limit)
    rejoin2 = api.post("/api/sessions/join/", body, format="json")
    assert rejoin2.status_code == 201
    assert rejoin2.json()["client_token"] != rejoin1.json()["client_token"]


@pytest.mark.django_db
def test_finalize_answers_on_manual_close(session_setup):
    from quiz.models import Participant

    api = APIClient()
    host = session_setup.host_token
    join = api.post(
        "/api/sessions/join/",
        {
            "join_code": session_setup.join_code,
            "student_no": "S301",
            "display_name": "未答",
        },
        format="json",
    ).json()
    api.post(f"/api/sessions/{session_setup.id}/start/", HTTP_AUTHORIZATION=f"Bearer {host}")
    api.post(
        f"/api/sessions/{session_setup.id}/phase/",
        {"phase": "options", "timer_seconds": 30},
        HTTP_AUTHORIZATION=f"Bearer {host}",
        format="json",
    )
    api.post(
        f"/api/sessions/{session_setup.id}/phase/",
        {"phase": "closed"},
        HTTP_AUTHORIZATION=f"Bearer {host}",
        format="json",
    )
    participant = Participant.objects.get(client_token=join["client_token"])
    question = session_setup.current_question()
    assert Answer.objects.filter(
        session=session_setup,
        participant=participant,
        question=question,
    ).exists()


@pytest.mark.django_db
def test_duplicate_student_no(session_setup):
    api = APIClient()
    body = {
        "join_code": session_setup.join_code,
        "student_no": "S001",
        "display_name": "小明",
    }
    assert api.post("/api/sessions/join/", body, format="json").status_code == 201
    assert api.post("/api/sessions/join/", body, format="json").status_code == 400


@pytest.mark.django_db
def test_join_does_not_expose_stem(session_setup):
    api = APIClient()
    res = api.post(
        "/api/sessions/join/",
        {
            "join_code": session_setup.join_code,
            "student_no": "S010",
            "display_name": "匿名",
        },
        format="json",
    )
    assert res.status_code == 201
    body = res.json()
    assert "stem" not in body
    assert "stem_text" not in str(body)


@pytest.mark.django_db
def test_participant_me_no_stem(session_setup):
    api = APIClient()
    join = api.post(
        "/api/sessions/join/",
        {
            "join_code": session_setup.join_code,
            "student_no": "S011",
            "display_name": "小安",
        },
        format="json",
    ).json()
    res = api.get(
        "/api/participants/me/",
        HTTP_AUTHORIZATION=f"Bearer {join['client_token']}",
    )
    assert res.status_code == 200
    body = res.json()
    assert "stem" not in body
    assert "stem_text" not in body
    assert "question" in body or body.get("current_question_id") is None


@pytest.mark.django_db
def test_flow_stem_options_submit(session_setup):
    api = APIClient()
    host = session_setup.host_token

    join = api.post(
        "/api/sessions/join/",
        {
            "join_code": session_setup.join_code,
            "student_no": "S002",
            "display_name": "小華",
        },
        format="json",
    ).json()
    client = join["client_token"]

    assert (
        api.post(
            f"/api/sessions/{session_setup.id}/start/",
            HTTP_AUTHORIZATION=f"Bearer {host}",
        ).status_code
        == 200
    )

    assert (
        api.post(
            f"/api/sessions/{session_setup.id}/phase/",
            {"phase": "options", "timer_seconds": 30},
            HTTP_AUTHORIZATION=f"Bearer {host}",
        ).status_code
        == 200
    )

    opts = api.post(
        "/api/participants/me/options/",
        HTTP_AUTHORIZATION=f"Bearer {client}",
    ).json()
    assert len(opts["options"]) == 2
    opt_id = opts["options"][0]["id"]

    sub = api.post(
        "/api/participants/me/answers/",
        {"option_ids": [opt_id]},
        HTTP_AUTHORIZATION=f"Bearer {client}",
        format="json",
    )
    assert sub.status_code == 201
    assert "score" in sub.json()["answer"]


@pytest.mark.django_db
def test_shuffle_differs(session_setup):
    api = APIClient()
    host = session_setup.host_token

    def join_student(no):
        r = api.post(
            "/api/sessions/join/",
            {
                "join_code": session_setup.join_code,
                "student_no": no,
                "display_name": no,
            },
            format="json",
        ).json()
        return r["client_token"]

    join_student("S101")
    join_student("S102")
    api.post(f"/api/sessions/{session_setup.id}/start/", HTTP_AUTHORIZATION=f"Bearer {host}")
    api.post(
        f"/api/sessions/{session_setup.id}/phase/",
        {"phase": "options"},
        HTTP_AUTHORIZATION=f"Bearer {host}",
    )

    def fetch_options(no):
        participant = session_setup.participants.get(student_no=no)
        opts = api.post(
            "/api/participants/me/options/",
            HTTP_AUTHORIZATION=f"Bearer {participant.client_token}",
        ).json()
        return [o["id"] for o in opts["options"]]

    order1 = fetch_options("S101")
    order2 = fetch_options("S102")
    assert order1 != order2 or len(order1) <= 1


@pytest.mark.django_db
def test_phase_over_http(live_server, bank):
    """真實 HTTP（非 APIClient）驗證 /phase/ 不會卡住。"""
    import json
    from urllib import request as urlrequest

    from quiz.services.session_fsm import create_session

    def post(path: str, payload: dict | None = None) -> dict:
        body = json.dumps(payload or {}).encode("utf-8")
        req = urlrequest.Request(
            f"{live_server.url.rstrip('/')}{path}",
            data=body,
            headers={
                "Authorization": f"Bearer {session.host_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlrequest.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())

    session = create_session(bank)
    post(f"/api/sessions/{session.id}/start/")
    data = post(f"/api/sessions/{session.id}/phase/", {"phase": "options", "timer_seconds": 30})
    assert data["current_phase"] == "options"
    assert data["phase_started_at"] is not None
    assert data["phase_timer_seconds"] == 30
    assert 29 <= data["phase_remaining_seconds"] <= 30


@pytest.mark.django_db
def test_adjust_timer_adds_remaining_seconds(session_setup):
    api = APIClient()
    host = session_setup.host_token
    api.post(f"/api/sessions/{session_setup.id}/start/", HTTP_AUTHORIZATION=f"Bearer {host}")
    api.post(
        f"/api/sessions/{session_setup.id}/phase/",
        {"phase": "options", "timer_seconds": 60},
        HTTP_AUTHORIZATION=f"Bearer {host}",
        format="json",
    )
    data = api.patch(
        f"/api/sessions/{session_setup.id}/timer/",
        {"timer_seconds": 25},
        HTTP_AUTHORIZATION=f"Bearer {host}",
        format="json",
    ).json()
    assert 82 <= data["phase_remaining_seconds"] <= 85
    assert data["phase_timer_seconds"] >= 84


@pytest.mark.django_db
def test_adjust_timer_negative_shortens(session_setup):
    api = APIClient()
    host = session_setup.host_token
    api.post(f"/api/sessions/{session_setup.id}/start/", HTTP_AUTHORIZATION=f"Bearer {host}")
    api.post(
        f"/api/sessions/{session_setup.id}/phase/",
        {"phase": "options", "timer_seconds": 60},
        HTTP_AUTHORIZATION=f"Bearer {host}",
        format="json",
    )
    data = api.patch(
        f"/api/sessions/{session_setup.id}/timer/",
        {"timer_seconds": -20},
        HTTP_AUTHORIZATION=f"Bearer {host}",
        format="json",
    ).json()
    assert 38 <= data["phase_remaining_seconds"] <= 42


@pytest.mark.django_db
def test_adjust_timer_negative_closes_when_zero(session_setup):
    api = APIClient()
    host = session_setup.host_token
    api.post(f"/api/sessions/{session_setup.id}/start/", HTTP_AUTHORIZATION=f"Bearer {host}")
    api.post(
        f"/api/sessions/{session_setup.id}/phase/",
        {"phase": "options", "timer_seconds": 30},
        HTTP_AUTHORIZATION=f"Bearer {host}",
        format="json",
    )
    data = api.patch(
        f"/api/sessions/{session_setup.id}/timer/",
        {"timer_seconds": -30},
        HTTP_AUTHORIZATION=f"Bearer {host}",
        format="json",
    ).json()
    assert data["current_phase"] == "closed"
    assert data["phase_remaining_seconds"] is None


@pytest.mark.django_db
def test_all_submitted_auto_closes_options(session_setup):
    api = APIClient()
    host = session_setup.host_token
    join_a = api.post(
        "/api/sessions/join/",
        {
            "join_code": session_setup.join_code,
            "student_no": "S301",
            "display_name": "A",
        },
        format="json",
    ).json()
    join_b = api.post(
        "/api/sessions/join/",
        {
            "join_code": session_setup.join_code,
            "student_no": "S302",
            "display_name": "B",
        },
        format="json",
    ).json()
    api.post(f"/api/sessions/{session_setup.id}/start/", HTTP_AUTHORIZATION=f"Bearer {host}")
    api.post(
        f"/api/sessions/{session_setup.id}/phase/",
        {"phase": "options", "timer_seconds": 120},
        HTTP_AUTHORIZATION=f"Bearer {host}",
        format="json",
    )

    for join in (join_a, join_b):
        opts = api.post(
            "/api/participants/me/options/",
            HTTP_AUTHORIZATION=f"Bearer {join['client_token']}",
        ).json()
        opt_id = opts["options"][0]["id"]
        api.post(
            "/api/participants/me/answers/",
            {"option_ids": [opt_id]},
            HTTP_AUTHORIZATION=f"Bearer {join['client_token']}",
            format="json",
        )

    session_setup.refresh_from_db()
    assert session_setup.current_phase == QuizSession.Phase.CLOSED
    assert Answer.objects.filter(session=session_setup).count() == 2


@pytest.mark.django_db
def test_session_summary_includes_average_and_stddev(session_setup):
    api = APIClient()
    host = session_setup.host_token
    join_a = api.post(
        "/api/sessions/join/",
        {
            "join_code": session_setup.join_code,
            "student_no": "S201",
            "display_name": "A",
        },
        format="json",
    ).json()
    join_b = api.post(
        "/api/sessions/join/",
        {
            "join_code": session_setup.join_code,
            "student_no": "S202",
            "display_name": "B",
        },
        format="json",
    ).json()
    api.post(f"/api/sessions/{session_setup.id}/start/", HTTP_AUTHORIZATION=f"Bearer {host}")

    api.post(
        f"/api/sessions/{session_setup.id}/phase/",
        {"phase": "options", "timer_seconds": 30},
        HTTP_AUTHORIZATION=f"Bearer {host}",
    )
    opts_a = api.post(
        "/api/participants/me/options/",
        HTTP_AUTHORIZATION=f"Bearer {join_a['client_token']}",
    ).json()
    opts_b = api.post(
        "/api/participants/me/options/",
        HTTP_AUTHORIZATION=f"Bearer {join_b['client_token']}",
    ).json()

    correct_a = next(opt["id"] for opt in opts_a["options"] if opt["label_text"] == "a")
    wrong_b = next(opt["id"] for opt in opts_b["options"] if opt["label_text"] != "a")

    api.post(
        "/api/participants/me/answers/",
        {"option_ids": [correct_a]},
        HTTP_AUTHORIZATION=f"Bearer {join_a['client_token']}",
        format="json",
    )
    api.post(
        "/api/participants/me/answers/",
        {"option_ids": [wrong_b]},
        HTTP_AUTHORIZATION=f"Bearer {join_b['client_token']}",
        format="json",
    )

    session_setup.refresh_from_db()
    summary = session_summary_payload(session_setup)
    assert summary["participant_count"] == 2
    assert "average_score" in summary
    assert "score_stddev" in summary
