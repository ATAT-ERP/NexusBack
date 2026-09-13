from django.db import migrations


def create_initial_company_roles(apps, schema_editor):
    CompanyRole = apps.get_model("companies", "CompanyRole")
    for code in ("owner", "member"):
        CompanyRole.objects.get_or_create(code=code)


class Migration(migrations.Migration):

    dependencies = [
        ("companies", "0003_companyrole_companymember"),
    ]

    operations = [
        migrations.RunPython(create_initial_company_roles, migrations.RunPython.noop),
    ]
