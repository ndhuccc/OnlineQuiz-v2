from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field

from django.contrib.auth.hashers import make_password

from quiz.models import UserProfile

HEADER_ALIASES = {
    "name": "name",
    "姓名": "name",
    "student_no": "student_no",
    "學號": "student_no",
    "學号": "student_no",
    "email": "email",
    "電子郵件": "email",
    "password": "password",
    "密碼": "password",
}


@dataclass
class UserImportError:
    index: int
    message: str


@dataclass
class UserImportResult:
    created_count: int = 0
    updated_count: int = 0
    errors: list[UserImportError] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return (self.created_count + self.updated_count) > 0


def _decode_csv_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp950", "big5"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("CSV 編碼無法解析，請使用 UTF-8 或 Excel 常見編碼另存")


def _normalize_header(name: str) -> str:
    key = name.strip()
    return HEADER_ALIASES.get(key, HEADER_ALIASES.get(key.lower(), key.lower()))


def _extract_row(row: dict[str, str], index: int) -> tuple[str, str, str, str]:
    normalized = {_normalize_header(key): (value or "").strip() for key, value in row.items()}
    name = normalized.get("name", "")
    student_no = normalized.get("student_no", "")
    email = normalized.get("email", "")
    password = normalized.get("password", "") or "test1234"
    if not name or not student_no or not email:
        raise ValueError("姓名、學號、email 都是必填欄位")
    return name, student_no, email, password


def import_users_from_csv_bytes(data: bytes) -> UserImportResult:
    text = _decode_csv_bytes(data)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("CSV 檔案缺少標題列")

    result = UserImportResult()
    for index, row in enumerate(reader, start=1):
        if not any((value or "").strip() for value in row.values()):
            continue
        try:
            name, student_no, email, password = _extract_row(row, index)
            _, created = UserProfile.objects.update_or_create(
                student_no=student_no,
                defaults={"name": name, "email": email, "password_hash": make_password(password)},
            )
            if created:
                result.created_count += 1
            else:
                result.updated_count += 1
        except Exception as exc:  # noqa: BLE001
            result.errors.append(UserImportError(index=index, message=str(exc)))

    return result