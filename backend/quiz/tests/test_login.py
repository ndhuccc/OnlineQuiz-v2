import pytest

from django.contrib.auth import get_user_model

from quiz.models import UserProfile


@pytest.mark.django_db
def test_teacher_login_endpoint():
    user_model = get_user_model()
    user_model.objects.create_user(username="teacher1", password="secret123", is_staff=True)

    from run_flask import app

    client = app.test_client()
    res = client.post(
        "/api/auth/login/",
        json={"role": "teacher", "username": "teacher1", "password": "secret123"},
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["role"] == "teacher"
    assert data["redirect_to"] == "/teacher"


@pytest.mark.django_db
def test_student_login_endpoint():
    user = UserProfile.objects.create(name="王小明", student_no="110001", email="ming@example.com")
    user.set_password("studpass123")
    user.save(update_fields=["password_hash"])

    from run_flask import app

    client = app.test_client()
    res = client.post(
        "/api/auth/login/",
        json={"role": "student", "student_no": "110001", "password": "studpass123"},
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["role"] == "student"
    assert data["display_name"] == "王小明"
    assert data["redirect_to"] == "/student"


@pytest.mark.django_db
def test_student_login_with_default_password():
    UserProfile.objects.create(name="張孝慈", student_no="110002", email="tzu@example.com")

    from run_flask import app

    client = app.test_client()
    res = client.post(
        "/api/auth/login/",
        json={"role": "student", "student_no": "110002", "password": "test1234"},
    )

    assert res.status_code == 200
    data = res.get_json()
    assert data["role"] == "student"
    assert data["display_name"] == "張孝慈"