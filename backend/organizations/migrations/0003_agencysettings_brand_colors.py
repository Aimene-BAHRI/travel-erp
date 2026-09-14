from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("organizations", "0002_agencysettings_onboarding")]

    operations = [
        migrations.AddField(
            model_name="agencysettings",
            name="primary_color",
            field=models.CharField(default="#0e7490", max_length=7),
        ),
        migrations.AddField(
            model_name="agencysettings",
            name="secondary_color",
            field=models.CharField(default="#0f172a", max_length=7),
        ),
    ]
