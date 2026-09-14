import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bookings", "0006_remove_legacy_amendment_reason")]

    operations = [
        migrations.CreateModel(
            name="BookingRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("reference", models.CharField(editable=False, max_length=24, unique=True)),
                ("customer_name", models.CharField(max_length=180)),
                ("phone", models.CharField(max_length=40)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("adults", models.PositiveSmallIntegerField(default=1)),
                ("children", models.PositiveSmallIntegerField(default=0)),
                ("infants", models.PositiveSmallIntegerField(default=0)),
                ("preferred_room_type", models.CharField(blank=True, max_length=100)),
                ("notes", models.TextField(blank=True)),
                ("consent", models.BooleanField(default=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("NEW", "New"),
                            ("CONTACTED", "Contacted"),
                            ("QUALIFIED", "Qualified"),
                            ("CONVERTED", "Converted"),
                            ("REJECTED", "Rejected"),
                        ],
                        default="NEW",
                        max_length=12,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "agency",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="booking_requests",
                        to="organizations.agency",
                    ),
                ),
                (
                    "trip",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="booking_requests",
                        to="trips.trip",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(
                        fields=["agency", "status", "created_at"],
                        name="bookings_bo_agency__e3df18_idx",
                    )
                ],
            },
        ),
    ]
