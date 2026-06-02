from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("quiz", "0010_remove_participant_rejoin_used"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="participant",
            name="rejoin_allowed",
        ),
    ]
