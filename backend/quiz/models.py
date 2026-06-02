import secrets
import string

from django.db import models
from django.utils import timezone
from django.contrib.auth.hashers import check_password, make_password


def generate_join_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


def generate_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


class QuestionBank(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    default_points = models.DecimalField(max_digits=8, decimal_places=2, default=1)
    default_timer_seconds = models.PositiveIntegerField(default=90)
    imported_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-imported_at"]

    def __str__(self) -> str:
        return self.name

    @property
    def question_count(self) -> int:
        return self.questions.count()


class UserProfile(models.Model):
    name = models.CharField(max_length=128)
    student_no = models.CharField(max_length=64, unique=True)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=128, blank=True, default="")
    login_token = models.CharField(max_length=64, blank=True, default="", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student_no"]

    def __str__(self) -> str:
        return f"{self.student_no} {self.name}"

    def set_password(self, raw_password: str) -> None:
        self.password_hash = make_password(raw_password)

    def save(self, *args, **kwargs) -> None:
        if not self.password_hash:
            self.set_password("test1234")
        super().save(*args, **kwargs)

    def check_password(self, raw_password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password(raw_password, self.password_hash)


class Question(models.Model):
    class Type(models.TextChoices):
        SINGLE = "single", "單選"
        MULTIPLE = "multiple", "多選"

    bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    order_index = models.PositiveIntegerField()
    stem_text = models.TextField()
    type = models.CharField(max_length=16, choices=Type.choices)
    category = models.CharField(max_length=512)
    question_type_tag = models.CharField(max_length=64, blank=True, default="")
    points = models.DecimalField(max_digits=8, decimal_places=2)
    timer_seconds = models.PositiveIntegerField()
    explanation_text = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["order_index"]
        constraints = [
            models.UniqueConstraint(
                fields=["bank", "order_index"],
                name="unique_question_order_per_bank",
            )
        ]

    def __str__(self) -> str:
        return f"Q{self.order_index + 1}: {self.stem_text[:40]}..."


class Option(models.Model):
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
    )
    letter = models.CharField(max_length=1)
    label_text = models.TextField()
    is_correct = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField()

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["question", "letter"],
                name="unique_option_letter_per_question",
            )
        ]

    def __str__(self) -> str:
        return f"{self.letter}. {self.label_text[:30]}"


class QuizSession(models.Model):
    class Status(models.TextChoices):
        LOBBY = "lobby", "大廳"
        RUNNING = "running", "進行中"
        SUMMARY = "summary", "總結"
        REVIEW = "review", "複習"
        CLOSED = "closed", "已關閉"

    class Phase(models.TextChoices):
        STEM = "stem", "題幹"
        OPTIONS = "options", "選項作答"
        CLOSED = "closed", "本題結束"

    bank = models.ForeignKey(
        QuestionBank,
        on_delete=models.PROTECT,
        related_name="sessions",
    )
    join_code = models.CharField(max_length=6, unique=True, db_index=True)
    host_token = models.CharField(max_length=64, unique=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.LOBBY,
    )
    current_question_index = models.PositiveIntegerField(default=0)
    current_phase = models.CharField(
        max_length=16,
        choices=Phase.choices,
        default=Phase.STEM,
    )
    phase_ends_at = models.DateTimeField(null=True, blank=True)
    phase_started_at = models.DateTimeField(null=True, blank=True)
    phase_timer_seconds = models.PositiveIntegerField(null=True, blank=True)
    question_snapshot = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Session {self.join_code} ({self.status})"

    @property
    def question_ids(self) -> list[int]:
        return list(self.question_snapshot)

    def current_question(self) -> Question | None:
        ids = self.question_ids
        if self.current_question_index >= len(ids):
            return None
        return Question.objects.filter(pk=ids[self.current_question_index]).first()


class Participant(models.Model):
    session = models.ForeignKey(
        QuizSession,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    student_no = models.CharField(max_length=64)
    display_name = models.CharField(max_length=128)
    client_token = models.CharField(max_length=64, unique=True)
    rejoin_allowed = models.BooleanField(default=False)
    rejoin_used = models.BooleanField(default=False)
    start_question_index = models.IntegerField(default=0)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "student_no"],
                name="unique_student_no_per_session",
            )
        ]
        ordering = ["joined_at"]

    def __str__(self) -> str:
        return f"{self.student_no} {self.display_name}"


class OptionShuffle(models.Model):
    session = models.ForeignKey(QuizSession, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    permutation = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "question", "participant"],
                name="unique_shuffle_per_participant_question",
            )
        ]


class Answer(models.Model):
    class SubmitSource(models.TextChoices):
        MANUAL = "manual", "手動"
        AUTO_TIMEOUT = "auto_timeout", "逾時自動"

    session = models.ForeignKey(QuizSession, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="answers")
    selected_option_ids = models.JSONField(default=list)
    score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    is_full_score = models.BooleanField(default=False)
    submit_source = models.CharField(
        max_length=16,
        choices=SubmitSource.choices,
        default=SubmitSource.MANUAL,
    )
    submitted_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "question", "participant"],
                name="unique_answer_per_question",
            )
        ]
        ordering = ["submitted_at"]
