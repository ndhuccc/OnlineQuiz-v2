from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import authenticate

from quiz.models import UserProfile


@dataclass
class LoginResult:
    role: str
    display_name: str
    identifier: str
    redirect_to: str
    token: str | None = None

    def as_dict(self) -> dict:
        data = {
            "role": self.role,
            "display_name": self.display_name,
            "identifier": self.identifier,
            "redirect_to": self.redirect_to,
        }
        if self.token is not None:
            data["token"] = self.token
        return data


def login_teacher(*, username: str, password: str) -> LoginResult:
    user = authenticate(username=username, password=password)
    if not user or not user.is_staff:
        raise ValueError("教師帳號或密碼錯誤")
    display_name = user.get_full_name().strip() or user.username
    return LoginResult(
        role="teacher",
        display_name=display_name,
        identifier=user.username,
        redirect_to="/teacher",
    )


def login_student(*, student_no: str, password: str) -> LoginResult:
    profile = UserProfile.objects.filter(student_no=student_no.strip()).first()
    if not profile:
        raise ValueError("學號或密碼錯誤")
    if not profile.check_password(password):
        raise ValueError("學號或密碼錯誤")
    from quiz.models import generate_token
    token = generate_token(32)
    profile.login_token = token
    profile.save(update_fields=["login_token"])
    return LoginResult(
        role="student",
        display_name=profile.name,
        identifier=profile.student_no,
        redirect_to="/student",
        token=token,
    )