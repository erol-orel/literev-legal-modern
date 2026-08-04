from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("literev", "0025_remove_project_elastic_search_query"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="language",
            field=models.CharField(
                blank=True, default="", max_length=8, null=True
            ),
        ),
    ]
