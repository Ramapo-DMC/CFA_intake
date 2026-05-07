from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("donations", "0011_donation_email_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="DonationCounter",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("current", models.PositiveSmallIntegerField(default=0)),
            ],
            options={
                "verbose_name": "donation counter",
            },
        ),
        migrations.AddField(
            model_name="donation",
            name="cdonation_number",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
