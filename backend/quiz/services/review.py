"""Post-quiz review data for students."""
from __future__ import annotations

from quiz.models import Answer, Option, Participant, Question, QuizSession


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

        answer = Answer.objects.filter(
            session=session,
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
            total_score += score
            selected_letters = sorted(
                Option.objects.filter(
                    pk__in=answer.selected_option_ids,
                    question=question,
                ).values_list("letter", flat=True)
            )

        options_display = [
            {"letter": o.letter, "label_text": o.label_text}
            for o in question.options.order_by("sort_order")
        ]

        questions_data.append(
            {
                "question_index": idx,
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
        )

    return {
        "session_id": session.id,
        "student_no": participant.student_no,
        "display_name": participant.display_name,
        "total_score": round(total_score, 2),
        "max_total_score": round(max_total, 2),
        "questions": questions_data,
    }
