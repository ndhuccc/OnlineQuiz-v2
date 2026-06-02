from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quiz", "0011_remove_participant_rejoin_allowed"),
    ]

    operations = [
        migrations.AddField(
            model_name="participant",
            name="active_tab_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="participant",
            name="last_seen_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
