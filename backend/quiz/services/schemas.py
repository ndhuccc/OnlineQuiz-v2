"""Pydantic schemas for questions.json import validation."""
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_OUTER_BRACKET_RE = re.compile(r"^\[(.*)\]\s*$", re.DOTALL)


def strip_outer_brackets(value):
    """Strip a single outer ``[...]`` wrapper if present.

    The bilingual question/option/explanation text is conventionally
    enclosed in square brackets (e.g. ``[題幹 (stem)]``); this helper
    unwraps that shell so downstream code and storage see clean text.
    """
    if not isinstance(value, str):
        return value
    s = value.strip()
    m = _OUTER_BRACKET_RE.match(s)
    return m.group(1).strip() if m else s


class ImportQuestionItem(BaseModel):
    node: str = Field(min_length=1)
    question_type: str = ""
    format: Literal["Single Choice", "Multiple Choice"]
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=2, max_length=10)
    correct_answer: str = Field(min_length=1)
    explanation: str = ""

    @field_validator("question", "explanation", mode="before")
    @classmethod
    def _strip_brackets_text(cls, v):
        return strip_outer_brackets(v)

    @field_validator("options", mode="before")
    @classmethod
    def _strip_brackets_list(cls, v):
        if not isinstance(v, list):
            return v
        return [strip_outer_brackets(item) for item in v]

    @field_validator("options")
    @classmethod
    def validate_options_not_empty(cls, v: list[str]) -> list[str]:
        if any(not s.strip() for s in v):
            raise ValueError("選項不可為空")
        return v


class ImportPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    default_points: float = Field(default=1.0, gt=0)
    default_timer_seconds: int = Field(default=90, ge=5, le=3600)
    questions: list[ImportQuestionItem] = Field(min_length=1)
