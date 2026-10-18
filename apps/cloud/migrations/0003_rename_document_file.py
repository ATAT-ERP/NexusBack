from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0002_document_company_fk"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="Document",
            new_name="File",
        ),
    ]
