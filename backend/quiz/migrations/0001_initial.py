# Generated manually for Phase 1

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="QuestionBank",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "default_points",
                    models.DecimalField(decimal_places=2, default=1, max_digits=8),
                ),
                ("default_timer_seconds", models.PositiveIntegerField(default=90)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-imported_at"],
            },
        ),
        migrations.CreateModel(
            name="Question",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order_index", models.PositiveIntegerField()),
                ("stem_text", models.TextField()),
                (
                    "type",
                    models.CharField(
                        choices=[("single", "單選"), ("multiple", "多選")],
                        max_length=16,
                    ),
                ),
                ("category", models.CharField(max_length=512)),
                (
                    "question_type_tag",
                    models.CharField(blank=True, default="", max_length=64),
                ),
                ("points", models.DecimalField(decimal_places=2, max_digits=8)),
                ("timer_seconds", models.PositiveIntegerField()),
                ("explanation_text", models.TextField(blank=True, default="")),
                (
                    "bank",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="questions",
                        to="quiz.questionbank",
                    ),
                ),
            ],
            options={
                "ordering": ["order_index"],
            },
        ),
        migrations.CreateModel(
            name="Option",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("letter", models.CharField(max_length=1)),
                ("label_text", models.TextField()),
                ("is_correct", models.BooleanField(default=False)),
                ("sort_order", models.PositiveIntegerField()),
                (
                    "question",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="options",
                        to="quiz.question",
                    ),
                ),
            ],
            options={
                "ordering": ["sort_order"],
            },
        ),
        migrations.AddConstraint(
            model_name="question",
            constraint=models.UniqueConstraint(
                fields=("bank", "order_index"),
                name="unique_question_order_per_bank",
            ),
        ),
        migrations.AddConstraint(
            model_name="option",
            constraint=models.UniqueConstraint(
                fields=("question", "letter"),
                name="unique_option_letter_per_question",
            ),
        ),
    ]
