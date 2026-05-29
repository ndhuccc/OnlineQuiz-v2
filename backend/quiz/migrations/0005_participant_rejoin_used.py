from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quiz", "0004_participant_rejoin_allowed"),
    ]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="rejoin_used",
            field=models.BooleanField(default=False),
        ),
    ]
