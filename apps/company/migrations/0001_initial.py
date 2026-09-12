from django.db import migrations, models

import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('type', models.CharField(choices=[('individual', 'Individual'), ('organization', 'Organization')], default='individual', max_length=20)),
                ('name', models.CharField(max_length=255)),
                ('legal_name', models.CharField(blank=True, max_length=255, null=True)),
                ('tax_id', models.CharField(blank=True, max_length=20, null=True)),
                ('email', models.EmailField(blank=True, max_length=254, null=True)),
                ('phone', models.CharField(blank=True, max_length=30, null=True)),
                ('address_street', models.CharField(blank=True, max_length=255, null=True)),
                ('address_number', models.CharField(blank=True, max_length=20, null=True)),
                ('address_city', models.CharField(blank=True, max_length=100, null=True)),
                ('address_postal_code', models.CharField(blank=True, max_length=20, null=True)),
                ('address_province', models.CharField(blank=True, max_length=100, null=True)),
                ('address_country', models.CharField(blank=True, max_length=100, null=True)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'companies',
            },
        ),
    ]
