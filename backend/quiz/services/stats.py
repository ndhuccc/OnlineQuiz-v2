"""Statistics for teacher dashboards."""
from __future__ import annotations

from decimal import Decimal
from math import sqrt

from django.db.models import Sum

from quiz.models import Answer, Question, QuizSession


def _pie_slices(full: int, partial: int, zero: int) -> dict:
    return {
        "labels": ["Full Score", "Partial Score", "No Score"],
        "counts": [full, partial, zero],
        "colors": ["#22c55e", "#f59e0b", "#ef4444"],
    }


def question_stats_payload(session: QuizSession, question: Question) -> dict:
    answers = Answer.objects.filter(session=session, question=question)
    full = answers.filter(is_full_score=True).count()
    partial = answers.filter(is_full_score=False, score__gt=0).count()
    zero = answers.filter(score=0).count()
    submitted = answers.count()
    participants = session.participants.count()

    return {
        "question_id": question.id,
        "question_index": session.current_question_index,
        "max_points": str(question.points),
        "submitted_count": submitted,
        "total_participants": participants,
        "full_score_count": full,
        "answer_rate": round(full / submitted, 4) if submitted else 0.0,
        "pie": _pie_slices(full, partial, zero),
    }


def session_summary_payload(session: QuizSession) -> dict:
    question_ids = session.question_ids
    questions = {
        q.id: q
        for q in Question.objects.filter(pk__in=question_ids).prefetch_related("options")
    }
    max_total = sum(float(questions[qid].points) for qid in question_ids if qid in questions)

    participant_scores: list[dict] = []
    total_scores: list[float] = []
    full_count = 0
    high_count = 0
    mid_count = 0
    low_count = 0
    zero_count = 0

    for participant in session.participants.all():
        total = (
            Answer.objects.filter(session=session, participant=participant)
            .aggregate(s=Sum("score"))
            .get("s")
            or Decimal("0")
        )
        total_f = float(total)
        total_scores.append(total_f)
        pct = (total_f / max_total * 100) if max_total > 0 else 0.0
        participant_scores.append(
            {
                "student_no": participant.student_no,
                "display_name": participant.display_name,
                "total_score": round(total_f, 2),
                "percentage": round(pct, 1),
            }
        )

        if max_total <= 0:
            zero_count += 1
        elif total_f >= max_total - 0.001:
            full_count += 1
        elif pct >= 80:
            high_count += 1
        elif pct >= 40:
            mid_count += 1
        elif total_f > 0:
            low_count += 1
        else:
            zero_count += 1

    participant_count = len(total_scores)
    average_score = sum(total_scores) / participant_count if participant_count else 0.0
    average_percentage = (average_score / max_total * 100) if max_total > 0 else 0.0
    score_variance = (
        sum((score - average_score) ** 2 for score in total_scores) / participant_count
        if participant_count
        else 0.0
    )
    score_stddev = sqrt(score_variance)

    question_rates = []
    for idx, qid in enumerate(question_ids):
        question = questions.get(qid)
        if not question:
            continue
        submitted = Answer.objects.filter(session=session, question=question).count()
        full = Answer.objects.filter(
            session=session, question=question, is_full_score=True
        ).count()
        question_rates.append(
            {
                "question_index": idx,
                "question_id": qid,
                "category": question.category,
                "points": str(question.points),
                "submitted_count": submitted,
                "full_score_count": full,
                "answer_rate": round(full / submitted, 4) if submitted else 0.0,
            }
        )

    return {
        "session_id": session.id,
        "join_code": session.join_code,
        "status": session.status,
        "max_total_score": round(max_total, 2),
        "participant_count": participant_count,
        "average_score": round(average_score, 2),
        "average_percentage": round(average_percentage, 1),
        "score_stddev": round(score_stddev, 2),
        "total_score_pie": {
            "labels": ["Perfect", "80-99%", "40-79%", "1-39%", "0%"],
            "counts": [full_count, high_count, mid_count, low_count, zero_count],
            "colors": ["#22c55e", "#84cc16", "#f59e0b", "#fb923c", "#ef4444"],
        },
        "participant_scores": sorted(
            participant_scores, key=lambda item: item["total_score"], reverse=True
        ),
        "question_rates": question_rates,
    }
