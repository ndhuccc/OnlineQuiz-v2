"""Pydantic schemas for questions.json import validation."""
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ImportQuestionItem(BaseModel):
    node: str = Field(min_length=1)
    question_type: str = ""
    format: Literal["Single Choice", "Multiple Choice"]
    question: str = Field(min_length=1)
    options: list[str] = Field(min_length=2, max_length=10)
    correct_answer: str = Field(min_length=1)
    explanation: str = ""

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
