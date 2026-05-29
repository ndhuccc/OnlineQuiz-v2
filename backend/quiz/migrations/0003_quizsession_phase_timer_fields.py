from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quiz", "0002_quizsession_participant_answer"),
    ]

    operations = [
        migrations.AddField(
            model_name="quizsession",
            name="phase_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="quizsession",
            name="phase_timer_seconds",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
