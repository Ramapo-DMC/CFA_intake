from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('donations', '0009_add_anonymous_donor_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='donation',
            name='address',
            field=models.TextField(blank=True),
        ),
    ]
