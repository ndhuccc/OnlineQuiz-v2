"""Per-participant option shuffling."""
from __future__ import annotations

import random

from quiz.models import Option, OptionShuffle, Participant, Question, QuizSession


def get_or_create_shuffle(
    session: QuizSession,
    question: Question,
    participant: Participant,
) -> list[int]:
    existing = OptionShuffle.objects.filter(
        session=session,
        question=question,
        participant=participant,
    ).first()
    if existing:
        return list(existing.permutation)

    option_ids = list(
        question.options.order_by("sort_order").values_list("id", flat=True)
    )
    random.shuffle(option_ids)
    OptionShuffle.objects.create(
        session=session,
        question=question,
        participant=participant,
        permutation=option_ids,
    )
    return option_ids


def shuffled_options_payload(question: Question, permutation: list[int]) -> list[dict]:
    options_map = {o.id: o for o in question.options.all()}
    result = []
    for idx, opt_id in enumerate(permutation):
        opt = options_map.get(opt_id)
        if not opt:
            continue
        result.append(
            {
                "id": opt.id,
                "display_letter": chr(ord("A") + idx),
                "label_text": opt.label_text,
            }
        )
    return result
