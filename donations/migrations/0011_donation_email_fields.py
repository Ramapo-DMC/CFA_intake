import secrets
from django.db import migrations, models


def generate_unsubscribe_tokens(apps, schema_editor):
    Donation = apps.get_model("donations", "Donation")
    for donation in Donation.objects.filter(unsubscribe_token__isnull=True):
        donation.unsubscribe_token = secrets.token_urlsafe(32)
        donation.save(update_fields=["unsubscribe_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("donations", "0010_alter_donation_address"),
    ]

    operations = [
        migrations.AddField(
            model_name="donation",
            name="opt_in_email",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="donation",
            name="unsubscribe",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="donation",
            name="unsubscribe_token",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
        migrations.RunPython(generate_unsubscribe_tokens, migrations.RunPython.noop),
    ]
