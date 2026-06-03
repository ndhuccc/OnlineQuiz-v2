import json

import pytest

from quiz.models import Option, Question, QuestionBank
from quiz.services.import_json import (
    import_from_json_text,
    import_question_bank,
    normalize_option_text,
    parse_option_line,
    validate_question_row,
)
from quiz.services.schemas import (
    ImportPayload,
    ImportQuestionItem,
    strip_outer_brackets,
)


def test_strip_outer_brackets_unwraps():
    assert strip_outer_brackets("[hello (world)]") == "hello (world)"


def test_strip_outer_brackets_preserves_plain_text():
    assert strip_outer_brackets("hello world") == "hello world"


def test_strip_outer_brackets_handles_internal_brackets():
    assert strip_outer_brackets("[設 T: ℝⁿ → ℝᵐ (text)]") == "設 T: ℝⁿ → ℝᵐ (text)"


def test_normalize_option_text_strips_legacy_prefix():
    assert normalize_option_text("A. 第一個選項") == "第一個選項"


def test_normalize_option_text_passes_plain_text():
    assert normalize_option_text("第一個選項") == "第一個選項"


def test_parse_option_line_strips_legacy_prefix():
    letter, text = parse_option_line("C", "C. 舊式選項內文")
    assert letter == "C"
    assert text == "舊式選項內文"


def test_parse_option_line_passes_through_clean_text():
    letter, text = parse_option_line("A", "新格式純文字")
    assert letter == "A"
    assert text == "新格式純文字"


def test_parse_option_line_does_not_strip_brackets():
    """Bracket stripping is the schema's job, not parse_option_line's.
    The schema before-validator unwraps [...]; by the time parse_option_line
    runs, the text is already clean. This test pins down that contract."""
    letter, text = parse_option_line("B", "[尚未剝括號的選項]")
    assert letter == "B"
    assert text == "[尚未剝括號的選項]"


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


def test_schema_strips_outer_brackets_from_question_and_explanation():
    item = ImportQuestionItem(
        node="n",
        format="Multiple Choice",
        question="[題幹 (stem)]",
        options=["[選項 A (option A)]", "[選項 B (option B)]"],
        correct_answer="A",
        explanation="[解析 (explanation)]",
    )
    assert item.question == "題幹 (stem)"
    assert item.explanation == "解析 (explanation)"
    assert item.options == ["選項 A (option A)", "選項 B (option B)"]


def test_schema_keeps_legacy_format_unchanged():
    item = ImportQuestionItem(
        node="n",
        format="Single Choice",
        question="題幹",
        options=["A. 一", "B. 二"],
        correct_answer="A",
    )
    assert item.options == ["A. 一", "B. 二"]


def test_validate_letter_assigned_by_index_not_text():
    item = ImportQuestionItem(
        node="n",
        format="Multiple Choice",
        question="[q]",
        options=[
            "[B 的描述]",  # 內文以 B 開頭但 index=0 → 應為 A
            "[A 的描述]",  # 內文以 A 開頭但 index=1 → 應為 B
            "[C 的描述]",
        ],
        correct_answer="AC",
    )
    qtype, opts, correct = validate_question_row(item)
    assert [o[0] for o in opts] == ["A", "B", "C"]
    assert opts[0][1] == "B 的描述"
    assert opts[1][1] == "A 的描述"
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
def test_import_new_bracket_format():
    """End-to-end: a payload matching the standard bracket-wrapped format
    (see linear-transform-standard-matrix.json) imports correctly with
    clean text, letters A-E by index, and is_correct matching correct_answer."""
    payload = ImportPayload(
        name="線性變換題庫",
        questions=[
            ImportQuestionItem(
                node="標準矩陣的定義",
                question_type="Knowledge",
                format="Multiple Choice",
                question="[A 的第 j 欄等於 T(eⱼ) (The j-th column equals T(eⱼ))]",
                options=[
                    "[第 j 欄等於 T(eⱼ) (col j = T(eⱼ))]",
                    "[第 j 列等於 T(eⱼ) (row j = T(eⱼ))]",
                    "[T(x) = Ax 對所有 x 成立 (T(x) = Ax for all x)]",
                    "[A 是 m×n 矩陣 (A is m×n)]",
                    "[必須先知道 T 對所有向量的作用 (must know T on all vectors)]",
                ],
                correct_answer="ACD",
                explanation="[解析 (analysis)] (A)(C)(D) 正確；(B)(E) 錯誤，因為 T(eⱼ) 對應的是第 j **欄** 而非第 j 列。 [End of analysis]",
            ),
        ],
    )
    result = import_question_bank(payload)
    assert result.success
    assert result.imported_count == 1

    bank = QuestionBank.objects.get(pk=result.bank_id)
    q = bank.questions.get(order_index=0)
    assert q.stem_text == "A 的第 j 欄等於 T(eⱼ) (The j-th column equals T(eⱼ))"
    assert q.explanation_text.startswith("解析 (analysis)")
    assert q.explanation_text.endswith("End of analysis")  # outer wrapper stripped
    # Internal ']' (section markers like [解析...]) are preserved
    assert "解析 (analysis)]" in q.explanation_text
    assert q.type == "multiple"
    assert q.category == "標準矩陣的定義"
    assert q.question_type_tag == "Knowledge"

    letters = list(q.options.order_by("sort_order").values_list("letter", flat=True))
    assert letters == ["A", "B", "C", "D", "E"]
    correct_letters = set(
        q.options.filter(is_correct=True).values_list("letter", flat=True)
    )
    assert correct_letters == {"A", "C", "D"}


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
def test_import_from_questions_array_legacy():
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
def test_import_from_questions_array_bracket_format():
    data = [
        {
            "node": "N",
            "question_type": "Concept",
            "format": "Multiple Choice",
            "question": "[題幹 (stem)]",
            "options": [
                "[選項 A 的描述 (option A)]",
                "[選項 B 的描述 (option B)]",
                "[選項 C 的描述 (option C)]",
            ],
            "correct_answer": "AB",
            "explanation": "[解析 (explanation)]",
        }
    ]
    result = import_from_json_text(json.dumps(data), bank_name="新格式陣列匯入")
    assert result.success, result.errors
    bank = QuestionBank.objects.get(name="新格式陣列匯入")
    q = bank.questions.get(order_index=0)
    assert q.stem_text == "題幹 (stem)"
    assert q.explanation_text == "解析 (explanation)"
    assert q.options.count() == 3
    assert set(q.options.filter(is_correct=True).values_list("letter", flat=True)) == {"A", "B"}


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
