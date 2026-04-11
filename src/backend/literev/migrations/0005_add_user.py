from django.apps import apps
from django.db import migrations

set_user_when_empty = """
UPDATE literev_project
SET user_id=1
WHERE user_id IS NULL;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("literev", "0004_project_user"),
    ]

    operations = [migrations.RunSQL(set_user_when_empty)]
