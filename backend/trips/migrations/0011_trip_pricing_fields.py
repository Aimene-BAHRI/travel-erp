from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("reference", "0002_seed_financial_reference_data"),
        ("trips", "0010_triptransport_vehicle_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="trip",
            name="pricing_currency",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="priced_trips",
                to="reference.currency",
            ),
        ),
        migrations.AddField(
            model_name="trip",
            name="child_with_bed_discount",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="trip",
            name="child_without_bed_price",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="trip",
            name="infant_price",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddConstraint(
            model_name="trip",
            constraint=models.CheckConstraint(
                condition=models.Q(("child_with_bed_discount__isnull", True))
                | models.Q(("child_with_bed_discount__gte", 0)),
                name="trip_child_bed_discount_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="trip",
            constraint=models.CheckConstraint(
                condition=models.Q(("child_without_bed_price__isnull", True))
                | models.Q(("child_without_bed_price__gte", 0)),
                name="trip_child_no_bed_price_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="trip",
            constraint=models.CheckConstraint(
                condition=models.Q(("infant_price__isnull", True))
                | models.Q(("infant_price__gte", 0)),
                name="trip_infant_price_gte_0",
            ),
        ),
    ]