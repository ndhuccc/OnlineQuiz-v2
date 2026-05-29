import json

import pytest

from quiz.models import Option, Question, QuestionBank
from quiz.services.import_json import (
    import_from_json_text,
    import_question_bank,
    parse_option_line,
    validate_question_row,
)
from quiz.services.schemas import ImportPayload, ImportQuestionItem


def test_parse_option_line():
    letter, text = parse_option_line("A. 第一個選項")
    assert letter == "A"
    assert text == "第一個選項"


def test_validate_single_choice():
    item = ImportQuestionItem(
        node="測試",
        format="Single Choice",
        question="題幹",
        options=["A. 一", "B. 二", "C. 三"],
        correct_answer="B",
    )
    qtype, opts, correct = validate_question_row(item)
    assert qtype == "single"
    assert len(opts) == 3
    assert correct == {"B"}


def test_validate_multiple_choice():
    item = ImportQuestionItem(
        node="測試",
        format="Multiple Choice",
        question="題幹",
        options=["A. 一", "B. 二", "C. 三", "D. 四"],
        correct_answer="AC",
    )
    _, _, correct = validate_question_row(item)
    assert correct == {"A", "C"}


@pytest.mark.django_db
def test_import_question_bank():
    payload = ImportPayload(
        name="測試題庫",
        questions=[
            ImportQuestionItem(
                node="章節1",
                format="Single Choice",
                question="1+1=?",
                options=["A. 1", "B. 2"],
                correct_answer="B",
            ),
            ImportQuestionItem(
                node="章節2",
                format="Multiple Choice",
                question="選質數",
                options=["A. 2", "B. 4", "C. 3"],
                correct_answer="AC",
            ),
        ],
    )
    result = import_question_bank(payload)
    assert result.success
    assert result.imported_count == 2

    bank = QuestionBank.objects.get(pk=result.bank_id)
    assert bank.questions.count() == 2
    q1 = bank.questions.get(order_index=0)
    assert q1.options.filter(is_correct=True).count() == 1
    q2 = bank.questions.get(order_index=1)
    assert q2.options.filter(is_correct=True).count() == 2


@pytest.mark.django_db
def test_import_does_not_expose_correct_via_orm_check():
    payload = ImportPayload(
        name="密碼題庫",
        questions=[
            ImportQuestionItem(
                node="n",
                format="Single Choice",
                question="Q",
                options=["A. x", "B. y"],
                correct_answer="A",
            )
        ],
    )
    result = import_question_bank(payload)
    opt = Option.objects.filter(question__bank_id=result.bank_id).get(letter="A")
    assert opt.is_correct is True


@pytest.mark.django_db
def test_import_from_questions_array():
    data = [
        {
            "node": "N",
            "format": "Single Choice",
            "question": "Q?",
            "options": ["A. a", "B. b"],
            "correct_answer": "A",
        }
    ]
    result = import_from_json_text(json.dumps(data), bank_name="陣列匯入")
    assert result.success
    assert QuestionBank.objects.filter(name="陣列匯入").exists()


@pytest.mark.django_db
def test_import_invalid_correct_answer():
    payload = ImportPayload(
        name="錯誤題庫",
        questions=[
            ImportQuestionItem(
                node="n",
                format="Single Choice",
                question="Q",
                options=["A. a", "B. b"],
                correct_answer="Z",
            )
        ],
    )
    result = import_question_bank(payload)
    assert not result.success
    assert len(result.errors) == 1
    assert QuestionBank.objects.filter(name="錯誤題庫").count() == 0
