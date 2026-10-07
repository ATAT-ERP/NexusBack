import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0001_initial"),
        ("companies", "0002_company_unique_company_tax_id"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name="document",
                    name="company_id",
                    field=models.ForeignKey(
                        db_column="company_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="documents",
                        to="companies.company",
                    ),
                ),
            ],
            state_operations=[
                migrations.RenameField(
                    model_name="document",
                    old_name="company_id",
                    new_name="company",
                ),
                migrations.AlterField(
                    model_name="document",
                    name="company",
                    field=models.ForeignKey(
                        db_column="company_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="documents",
                        to="companies.company",
                    ),
                ),
            ],
        ),
    ]
