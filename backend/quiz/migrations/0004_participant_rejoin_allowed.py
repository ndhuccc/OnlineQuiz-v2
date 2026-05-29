from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quiz", "0003_quizsession_phase_timer_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="rejoin_allowed",
            field=models.BooleanField(default=False),
        ),
    ]
