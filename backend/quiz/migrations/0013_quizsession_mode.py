from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("quiz", "0012_participant_active_tab_last_seen"),
    ]

    operations = [
        migrations.AddField(
            model_name="quizsession",
            name="mode",
            field=models.CharField(
                choices=[("auto", "純自動模式"), ("manual", "評量講解模式")],
                default="auto",
                max_length=16,
            ),
        ),
    ]
