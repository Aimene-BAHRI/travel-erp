from django.db import migrations

class Migration(migrations.Migration):
    dependencies=[("trips","0007_trip_public_package_prices")]
    operations=[
        migrations.RemoveField(model_name="trip",name="public_adult_price"),
        migrations.RemoveField(model_name="trip",name="public_child_price"),
        migrations.RemoveField(model_name="trip",name="public_infant_price"),
        migrations.RemoveField(model_name="trip",name="public_price_currency"),
    ]
