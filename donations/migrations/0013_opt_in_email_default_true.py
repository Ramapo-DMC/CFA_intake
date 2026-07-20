from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("donations", "0012_cdonation_number"),
    ]

    operations = [
        migrations.AlterField(
            model_name="donation",
            name="opt_in_email",
            field=models.BooleanField(default=True),
        ),
    ]
