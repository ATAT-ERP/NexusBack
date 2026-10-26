import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_credit_notes"),
        ("documents", "0003_rename_document_file"),
    ]

    operations = [
        migrations.AddField(
            model_name=model_name,
            name="representation_file",
            field=models.OneToOneField(
                blank=True,
                editable=False,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="documents.file",
            ),
        )
        for model_name in ("invoice", "creditnote")
    ]
