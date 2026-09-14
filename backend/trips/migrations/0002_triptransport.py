import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_seed_airlines"), ("trips", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="TripTransport",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("mode", models.CharField(choices=[("BUS", "Bus"), ("PRIVATE_CAR", "Private car"), ("TRAIN", "Train"), ("FERRY", "Ferry"), ("OTHER", "Other")], max_length=12)),
                ("departure_at", models.DateTimeField()),
                ("arrival_at", models.DateTimeField()),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("vehicle_details", models.CharField(blank=True, max_length=180)),
                ("order", models.PositiveSmallIntegerField()),
                ("notes", models.TextField(blank=True)),
                ("destination_city", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="arriving_trip_transports", to="reference.city")),
                ("origin_city", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="departing_trip_transports", to="reference.city")),
                ("supplier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="trip_transports", to="catalog.supplier")),
                ("trip", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="transports", to="trips.trip")),
            ],
            options={"ordering": ["order", "departure_at"]},
        ),
        migrations.AddConstraint(model_name="triptransport", constraint=models.UniqueConstraint(fields=("trip", "order"), name="uniq_trip_transport_order")),
        migrations.AddConstraint(model_name="triptransport", constraint=models.CheckConstraint(condition=models.Q(("arrival_at__gt", models.F("departure_at"))), name="trip_transport_arrival_after_departure")),
        migrations.AddIndex(model_name="triptransport", index=models.Index(fields=["trip", "order"], name="trips_tript_trip_id_d50537_idx")),
    ]
