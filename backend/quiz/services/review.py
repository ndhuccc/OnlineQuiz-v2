"""Per-question and post-quiz review data for students."""
from __future__ import annotations

from quiz.models import Answer, Option, Participant, Question, QuizSession


def _question_review_entry(participant: Participant, question_index: int, question: Question) -> dict:
    """Build the per-question payload used by both full review and the
    just-closed question's reveal.
    """
    answer = Answer.objects.filter(
        session=participant.session,
        question=question,
        participant=participant,
    ).first()

    correct_letters = sorted(
        Option.objects.filter(question=question, is_correct=True).values_list(
            "letter", flat=True
        )
    )
    selected_letters: list[str] = []
    score = 0.0
    is_full = False
    submit_source = None

    if answer:
        score = float(answer.score)
        is_full = answer.is_full_score
        submit_source = answer.submit_source
        selected_letters = sorted(
            Option.objects.filter(
                pk__in=answer.selected_option_ids,
                question=question,
            ).values_list("letter", flat=True)
        )

    options_display = [
        {
            "id": o.id,
            "letter": o.letter,
            "label_text": o.label_text,
            "is_correct": o.is_correct,
            "is_your_answer": o.id in (answer.selected_option_ids if answer else []),
        }
        for o in question.options.order_by("sort_order")
    ]

    return {
        "question_index": question_index,
        "stem_text": question.stem_text,
        "type": question.type,
        "category": question.category,
        "points": str(question.points),
        "your_answer": "".join(selected_letters) if selected_letters else None,
        "correct_answer": "".join(correct_letters),
        "score": score,
        "is_full_score": is_full,
        "submit_source": submit_source,
        "explanation_text": question.explanation_text,
        "options": options_display,
    }


def current_question_result_payload(participant: Participant) -> dict:
    """Per-question reveal: only available after the current question's
    options phase is closed (i.e. in CLOSED/REVIEW). Used by MANUAL mode
    so students can see the correct answer + their score between questions.
    """
    session = participant.session
    session.refresh_from_db()

    # The current question's index may be past session.question_ids if
    # the session ended (status=REVIEW or CLOSED at session level).
    if session.current_question_index >= len(session.question_ids):
        raise ValueError("本場測驗已無進行中的題目")

    question_index = session.current_question_index
    question_id = session.question_ids[question_index]
    question = Question.objects.filter(pk=question_id).prefetch_related("options").first()
    if not question:
        raise ValueError("找不到題目")

    # Gate: only reveal once the question's options phase is closed.
    # For REVIEW status, the question is naturally closed.
    if session.status == QuizSession.Status.REVIEW:
        pass  # ok
    elif session.status == QuizSession.Status.RUNNING and session.current_phase == QuizSession.Phase.CLOSED:
        pass  # ok
    else:
        raise ValueError("本題尚未結束")

    entry = _question_review_entry(participant, question_index, question)
    return {
        "session_id": session.id,
        "question": entry,
    }


def participant_review_payload(participant: Participant) -> dict:
    session = participant.session
    if session.status not in (QuizSession.Status.REVIEW, QuizSession.Status.CLOSED):
        raise ValueError("教師尚未開放複習")

    questions_data = []
    total_score = 0.0
    max_total = 0.0

    for idx, qid in enumerate(session.question_ids):
        question = (
            Question.objects.filter(pk=qid).prefetch_related("options").first()
        )
        if not question:
            continue
        max_total += float(question.points)
        entry = _question_review_entry(participant, idx, question)
        questions_data.append(entry)
        # 累加分數（從 entry 算回來）
        total_score += entry["score"]

    return {
        "session_id": session.id,
        "student_no": participant.student_no,
        "display_name": participant.display_name,
        "total_score": round(total_score, 2),
        "max_total_score": round(max_total, 2),
        "questions": questions_data,
    }
