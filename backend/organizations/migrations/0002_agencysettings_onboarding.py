from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("organizations", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="agencysettings",
            name="invoice_footer",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="agencysettings",
            name="setup_status",
            field=models.CharField(
                choices=[("SETUP", "Setup"), ("READY", "Ready for review"), ("ACTIVE", "Active")],
                default="SETUP",
                max_length=10,
            ),
        ),
    ]
