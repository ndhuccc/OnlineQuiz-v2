import pytest
from django.contrib.auth.hashers import make_password
from quiz.models import UserProfile, QuizSession, QuestionBank, Question, Participant, Answer

@pytest.mark.django_db
def test_student_history_and_details():
    # 1. Create a student profile
    student = UserProfile.objects.create(
        name="測試學生",
        student_no="stud1",
        email="stud1@example.com",
        password_hash=make_password("stud1")
    )
    
    # Generate token
    from quiz.models import generate_token
    token = generate_token(32)
    student.login_token = token
    student.save()

    # 2. Setup QuestionBank, Question, QuizSession, Participant, Answer
    bank = QuestionBank.objects.create(name="線性代數單元一")
    question = Question.objects.create(
        bank=bank,
        order_index=0,
        stem_text="What is $1 + 1$?",
        type=Question.Type.SINGLE,
        points=2.5,
        timer_seconds=60,
        explanation_text="Clearly it is 2."
    )
    
    session = QuizSession.objects.create(
        bank=bank,
        join_code="ABCDEF",
        host_token="host123",
        question_snapshot=[question.id],
        status=QuizSession.Status.CLOSED
    )

    participant = Participant.objects.create(
        session=session,
        student_no="stud1",
        display_name="測試學生",
        client_token="client123"
    )

    Answer.objects.create(
        session=session,
        question=question,
        participant=participant,
        selected_option_ids=[],
        score=2.5,
        is_full_score=True
    )

    from run_flask import app
    client = app.test_client()

    # Query without token should fail
    res = client.get("/api/students/history/")
    assert res.status_code == 401

    # Query with token should succeed
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/students/history/", headers=headers)
    assert res.status_code == 200
    data = res.get_json()
    assert data["total_count"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["bank_name"] == "線性代數單元一"
    assert data["items"][0]["actual_score"] == 2.5
    assert data["items"][0]["max_score"] == 2.5

    # Get details
    p_id = data["items"][0]["participant_id"]
    res_detail = client.get(f"/api/students/history/{p_id}/", headers=headers)
    assert res_detail.status_code == 200
    detail_data = res_detail.get_json()
    assert detail_data["bank_name"] == "線性代數單元一"
    assert len(detail_data["questions"]) == 1
    assert detail_data["questions"][0]["explanation_text"] == "Clearly it is 2."


@pytest.mark.django_db
def test_join_requires_login_and_validates_student_no():
    # 1. Create student profile
    student = UserProfile.objects.create(
        name="測試學生",
        student_no="stud1",
        email="stud1@example.com",
        password_hash=make_password("stud1")
    )
    from quiz.models import generate_token
    token = generate_token(32)
    student.login_token = token
    student.save()

    # 2. Setup QuestionBank & Session
    bank = QuestionBank.objects.create(name="線性代數")
    session = QuizSession.objects.create(
        bank=bank,
        join_code="XYZW",
        host_token="hostxyz",
        question_snapshot=[],
        status=QuizSession.Status.LOBBY
    )

    from run_flask import app
    client = app.test_client()

    # Join without login token should yield 401
    payload = {
        "join_code": "XYZW",
        "student_no": "stud1",
        "display_name": "測試學生"
    }
    res_no_login = client.post("/api/sessions/join/", json=payload)
    assert res_no_login.status_code == 401
    assert "先以學生帳密登入" in res_no_login.get_json()["detail"]

    # Join with login token but mismatching student no should yield 403
    mismatch_payload = {
        "join_code": "XYZW",
        "student_no": "stud2", # student is logged in as stud1
        "display_name": "欺騙學生"
    }
    headers = {"Authorization": f"Bearer {token}"}
    res_mismatch = client.post("/api/sessions/join/", json=mismatch_payload, headers=headers)
    assert res_mismatch.status_code == 403
    assert "不符" in res_mismatch.get_json()["detail"]

    # Join with correct login token and student no should succeed (201)
    res_success = client.post("/api/sessions/join/", json=payload, headers=headers)
    assert res_success.status_code == 201
    assert "client_token" in res_success.get_json()

