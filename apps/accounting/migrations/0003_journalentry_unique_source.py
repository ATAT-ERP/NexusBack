from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounting", "0002_journalentry_journalline_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.UniqueConstraint(
                fields=("company", "source_type", "source_id"),
                condition=models.Q(source_id__isnull=False) & ~models.Q(source_id=""),
                name="unique_journal_entry_source",
            ),
        ),
    ]
