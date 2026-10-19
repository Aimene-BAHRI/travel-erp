from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("pricing", "0004_remove_triphotelprice_uniq_standard_trip_hotel_price_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="TripHotelFixedPrice",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("child_without_bed", models.DecimalField(decimal_places=4, max_digits=18)),
                ("infant", models.DecimalField(decimal_places=4, max_digits=18)),
                ("agency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trip_hotel_fixed_prices", to="organizations.agency")),
                ("currency", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="trip_hotel_fixed_prices", to="reference.currency")),
                ("trip_hotel", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="fixed_prices", to="trips.triphotel")),
            ],
            options={"constraints": [
                models.CheckConstraint(condition=models.Q(("child_without_bed__gte", 0)), name="trip_hotel_child_no_bed_gte_0"),
                models.CheckConstraint(condition=models.Q(("infant__gte", 0)), name="trip_hotel_infant_gte_0"),
            ]},
        ),
    ]