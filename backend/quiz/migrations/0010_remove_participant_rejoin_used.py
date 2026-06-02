from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("quiz", "0009_participant_start_question_index"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="participant",
            name="rejoin_used",
        ),
    ]
