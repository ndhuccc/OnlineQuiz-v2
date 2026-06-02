import pytest

from quiz.models import UserProfile
from quiz.services.user_import import import_users_from_csv_bytes


@pytest.mark.django_db
def test_import_users_from_csv_bytes_creates_records():
    csv_bytes = (
        "姓名,學號,email\n"
        "王小明,110001,ming@example.com\n"
        "李小華,110002,hua@example.com\n"
    ).encode("utf-8")

    result = import_users_from_csv_bytes(csv_bytes)

    assert result.success
    assert result.created_count == 2
    assert result.updated_count == 0
    assert not result.errors
    assert UserProfile.objects.filter(student_no="110001").exists()


@pytest.mark.django_db
def test_import_users_from_csv_bytes_updates_existing_record():
    UserProfile.objects.create(name="舊姓名", student_no="110003", email="old@example.com")
    csv_bytes = "姓名,學號,email\n新姓名,110003,new@example.com\n".encode("utf-8")

    result = import_users_from_csv_bytes(csv_bytes)

    assert result.success
    assert result.created_count == 0
    assert result.updated_count == 1
    user = UserProfile.objects.get(student_no="110003")
    assert user.name == "新姓名"
    assert user.email == "new@example.com"


@pytest.mark.django_db
def test_import_users_from_csv_bytes_supports_chinese_email_header():
    csv_bytes = (
        "姓名,學號,電子郵件\n"
        "陳小美,110004,mei@example.com\n"
    ).encode("cp950")

    result = import_users_from_csv_bytes(csv_bytes)

    assert result.success
    assert UserProfile.objects.filter(student_no="110004", email="mei@example.com").exists()


@pytest.mark.django_db
def test_import_users_default_password_is_test1234():
    csv_bytes = (
        "姓名,學號,email\n"
        "陳小強,110005,chiang@example.com\n"
    ).encode("utf-8")

    result = import_users_from_csv_bytes(csv_bytes)

    assert result.success
    profile = UserProfile.objects.get(student_no="110005")
    assert profile.check_password("test1234")