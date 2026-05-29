# Generated manually for Phase 2

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("quiz", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuizSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("join_code", models.CharField(db_index=True, max_length=6, unique=True)),
                ("host_token", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("lobby", "大廳"),
                            ("running", "進行中"),
                            ("summary", "總結"),
                            ("review", "複習"),
                            ("closed", "已關閉"),
                        ],
                        default="lobby",
                        max_length=16,
                    ),
                ),
                ("current_question_index", models.PositiveIntegerField(default=0)),
                (
                    "current_phase",
                    models.CharField(
                        choices=[
                            ("stem", "題幹"),
                            ("options", "選項作答"),
                            ("closed", "本題結束"),
                        ],
                        default="stem",
                        max_length=16,
                    ),
                ),
                ("phase_ends_at", models.DateTimeField(blank=True, null=True)),
                ("question_snapshot", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                (
                    "bank",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sessions",
                        to="quiz.questionbank",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Participant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("student_no", models.CharField(max_length=64)),
                ("display_name", models.CharField(max_length=128)),
                ("client_token", models.CharField(max_length=64, unique=True)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="participants",
                        to="quiz.quizsession",
                    ),
                ),
            ],
            options={"ordering": ["joined_at"]},
        ),
        migrations.CreateModel(
            name="OptionShuffle",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("permutation", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "participant",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="quiz.participant"),
                ),
                (
                    "question",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="quiz.question"),
                ),
                (
                    "session",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="quiz.quizsession"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Answer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("selected_option_ids", models.JSONField(default=list)),
                ("score", models.DecimalField(decimal_places=2, default=0, max_digits=8)),
                ("is_full_score", models.BooleanField(default=False)),
                (
                    "submit_source",
                    models.CharField(
                        choices=[("manual", "手動"), ("auto_timeout", "逾時自動")],
                        default="manual",
                        max_length=16,
                    ),
                ),
                ("submitted_at", models.DateTimeField(default=django.utils.timezone.now)),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answers",
                        to="quiz.participant",
                    ),
                ),
                (
                    "question",
                    models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="quiz.question"),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="answers",
                        to="quiz.quizsession",
                    ),
                ),
            ],
            options={"ordering": ["submitted_at"]},
        ),
        migrations.AddConstraint(
            model_name="participant",
            constraint=models.UniqueConstraint(
                fields=("session", "student_no"),
                name="unique_student_no_per_session",
            ),
        ),
        migrations.AddConstraint(
            model_name="optionshuffle",
            constraint=models.UniqueConstraint(
                fields=("session", "question", "participant"),
                name="unique_shuffle_per_participant_question",
            ),
        ),
        migrations.AddConstraint(
            model_name="answer",
            constraint=models.UniqueConstraint(
                fields=("session", "question", "participant"),
                name="unique_answer_per_question",
            ),
        ),
    ]
