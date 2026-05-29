"""Parse and import questions.json format into the database."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from django.db import transaction

from quiz.models import Option, Question, QuestionBank

from .schemas import ImportPayload, ImportQuestionItem

OPTION_PREFIX_RE = re.compile(r"^([A-Z])\.\s*(.*)$", re.DOTALL)
FORMAT_TO_TYPE = {
    "Single Choice": Question.Type.SINGLE,
    "Multiple Choice": Question.Type.MULTIPLE,
}


@dataclass
class ImportRowError:
    index: int  # 0-based in questions array
    message: str


@dataclass
class ImportResult:
    bank_id: int | None = None
    bank_name: str = ""
    imported_count: int = 0
    errors: list[ImportRowError] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.bank_id is not None and self.imported_count > 0


def parse_option_line(line: str) -> tuple[str, str]:
    m = OPTION_PREFIX_RE.match(line.strip())
    if not m:
        raise ValueError(f"選項格式錯誤，需以「A. 」開頭：{line[:40]}...")
    return m.group(1), m.group(2).strip()


def parse_correct_letters(answer: str, available: set[str], qtype: str) -> set[str]:
    letters = {c for c in answer.strip().upper() if c.isalpha()}
    invalid = letters - available
    if invalid:
        raise ValueError(f"正確答案含不存在的選項：{''.join(sorted(invalid))}")
    if not letters:
        raise ValueError("正確答案不可為空")
    if qtype == Question.Type.SINGLE and len(letters) != 1:
        raise ValueError("單選題正確答案只能有一個字母")
    return letters


def validate_question_row(item: ImportQuestionItem) -> tuple[Question.Type, list[tuple[str, str]], set[str]]:
    qtype = FORMAT_TO_TYPE[item.format]
    parsed_options: list[tuple[str, str]] = []
    letters_seen: set[str] = set()

    for raw in item.options:
        letter, text = parse_option_line(raw)
        if letter in letters_seen:
            raise ValueError(f"選項字母重複：{letter}")
        letters_seen.add(letter)
        parsed_options.append((letter, text))

    correct = parse_correct_letters(item.correct_answer, letters_seen, qtype)
    return qtype, parsed_options, correct


def load_import_payload(data: dict | list) -> ImportPayload:
    if isinstance(data, list):
        raise ValueError("請提供含 name 與 questions 的物件，或上傳完整匯入 JSON")
    return ImportPayload.model_validate(data)


def load_questions_array(data: list) -> ImportPayload:
    """Import from raw questions.json array with auto-generated bank name."""
    items = [ImportQuestionItem.model_validate(row) for row in data]
    return ImportPayload(
        name="匯入題庫",
        questions=items,
    )


@transaction.atomic
def import_question_bank(payload: ImportPayload) -> ImportResult:
    result = ImportResult(bank_name=payload.name)
    bank = QuestionBank.objects.create(
        name=payload.name,
        description=payload.description,
        default_points=payload.default_points,
        default_timer_seconds=payload.default_timer_seconds,
    )
    result.bank_id = bank.id

    for idx, item in enumerate(payload.questions):
        try:
            qtype, parsed_opts, correct_letters = validate_question_row(item)
            question = Question.objects.create(
                bank=bank,
                order_index=idx,
                stem_text=item.question,
                type=qtype,
                category=item.node,
                question_type_tag=item.question_type or "",
                points=payload.default_points,
                timer_seconds=payload.default_timer_seconds,
                explanation_text=item.explanation or "",
            )
            for sort_order, (letter, label) in enumerate(parsed_opts):
                Option.objects.create(
                    question=question,
                    letter=letter,
                    label_text=label,
                    is_correct=letter in correct_letters,
                    sort_order=sort_order,
                )
            result.imported_count += 1
        except Exception as exc:  # noqa: BLE001 — collect per-row errors
            result.errors.append(ImportRowError(index=idx, message=str(exc)))

    if result.imported_count == 0:
        bank.delete()
        result.bank_id = None
    return result


def import_from_json_text(
    text: str,
    *,
    bank_name: str | None = None,
    default_points: float = 1.0,
    default_timer_seconds: int = 90,
) -> ImportResult:
    raw = json.loads(text)
    if isinstance(raw, list):
        payload = load_questions_array(raw)
        if bank_name:
            payload.name = bank_name
        payload.default_points = default_points
        payload.default_timer_seconds = default_timer_seconds
    else:
        payload = load_import_payload(raw)
    return import_question_bank(payload)
