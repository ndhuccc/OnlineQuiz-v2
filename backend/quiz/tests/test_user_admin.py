import pytest

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from quiz.models import UserProfile


@pytest.mark.django_db
def test_userprofile_admin_import_page_accessible(client):
    user_model = get_user_model()
    admin_user = user_model.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="password123",
    )
    client.force_login(admin_user)

    response = client.get(reverse("admin:quiz_userprofile_import"))

    assert response.status_code == 200
    assert "CSV 匯入使用者" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_userprofile_admin_csv_import(client):
    user_model = get_user_model()
    admin_user = user_model.objects.create_superuser(
        username="admin2",
        email="admin2@example.com",
        password="password123",
    )
    client.force_login(admin_user)

    csv_content = "姓名,學號,email\n林小琪,110010,qi@example.com\n"
    response = client.post(
        reverse("admin:quiz_userprofile_import"),
        data={
            "csv_file": SimpleUploadedFile(
                "users.csv",
                csv_content.encode("utf-8"),
                content_type="text/csv",
            )
        },
    )

    assert response.status_code == 302
    assert UserProfile.objects.filter(student_no="110010", name="林小琪").exists()