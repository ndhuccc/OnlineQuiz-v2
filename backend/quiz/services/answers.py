"""Answer submission and grading."""
from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from quiz.models import Answer, Option, Participant, Question, QuizSession
from quiz.services.grading import grade_answer


def letters_for_options(question: Question, option_ids: list[int]) -> set[str]:
    if not option_ids:
        return set()
    letters = Option.objects.filter(
        question=question,
        pk__in=option_ids,
    ).values_list("letter", flat=True)
    return set(letters)


def correct_letters(question: Question) -> set[str]:
    return set(
        Option.objects.filter(question=question, is_correct=True).values_list(
            "letter", flat=True
        )
    )


def grade_question_answer(
    question: Question,
    selected_option_ids: list[int],
) -> tuple[Decimal, bool]:
    n = question.options.count()
    selected = letters_for_options(question, selected_option_ids)
    correct = correct_letters(question)
    score, is_full = grade_answer(
        n_options=n,
        correct_letters=correct,
        selected_letters=selected,
        points=float(question.points),
    )
    return Decimal(str(round(score, 4))), is_full


@transaction.atomic
def submit_answer(
    *,
    participant: Participant,
    question: Question,
    selected_option_ids: list[int],
    submit_source: str = Answer.SubmitSource.MANUAL,
) -> Answer:
    session = participant.session
    if Answer.objects.filter(
        session=session,
        question=question,
        participant=participant,
    ).exists():
        raise ValueError("本題已提交，不可重複作答")

    if selected_option_ids:
        valid = set(
            question.options.filter(pk__in=selected_option_ids).values_list("id", flat=True)
        )
        if len(valid) != len(set(selected_option_ids)):
            raise ValueError("包含無效的選項")

    score, is_full = grade_question_answer(question, selected_option_ids)
    return Answer.objects.create(
        session=session,
        question=question,
        participant=participant,
        selected_option_ids=selected_option_ids,
        score=score,
        is_full_score=is_full,
        submit_source=submit_source,
        submitted_at=timezone.now(),
    )


def auto_submit_empty(participant: Participant, question: Question) -> Answer | None:
    if Answer.objects.filter(
        session=participant.session,
        question=question,
        participant=participant,
    ).exists():
        return None
    return submit_answer(
        participant=participant,
        question=question,
        selected_option_ids=[],
        submit_source=Answer.SubmitSource.AUTO_TIMEOUT,
    )


def finalize_question_answers(session: QuizSession, question: Question) -> int:
    """本題結束：為尚未作答的學生寫入空答案與成績（已作答者保留原紀錄）。"""
    created = 0
    for participant in session.participants.all():
        if auto_submit_empty(participant, question):
            created += 1
    return created
