from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("companies", "0004_initial_company_roles"),
    ]

    operations = [
        migrations.CreateModel(
            name="FiscalProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "vat_condition",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (1, "IVA Responsable Inscripto"),
                            (4, "IVA Sujeto Exento"),
                            (5, "Consumidor Final"),
                            (6, "Responsable Monotributo"),
                            (13, "Monotributista Social"),
                            (15, "IVA No Alcanzado"),
                            (16, "Monotributo Trabajador Independiente Promovido"),
                        ]
                    ),
                ),
                ("gross_income", models.CharField(blank=True, max_length=30)),
                ("business_start_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="fiscal_profile",
                        to="companies.company",
                    ),
                ),
            ],
            options={"db_table": "billing_fiscal_profiles"},
        ),
    ]
