from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("trips", "0009_trip_max_travelers")]

    operations = [
        migrations.AddField(
            model_name="triptransport",
            name="vehicle_number",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]