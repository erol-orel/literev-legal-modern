from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("literev", "0026_document_language"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="tablechoice",
            index=models.Index(
                fields=["project", "user"], name="literev_tc_project_user_idx"
            ),
        ),
    ]
