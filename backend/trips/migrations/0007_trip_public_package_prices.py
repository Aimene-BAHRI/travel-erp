import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies=[("trips","0006_tripclosingitem_assigned_to_tripclosingitem_due_date")]
    operations=[
        migrations.AddField(model_name="trip",name="public_adult_price",field=models.DecimalField(blank=True,decimal_places=4,max_digits=18,null=True)),
        migrations.AddField(model_name="trip",name="public_child_price",field=models.DecimalField(blank=True,decimal_places=4,max_digits=18,null=True)),
        migrations.AddField(model_name="trip",name="public_infant_price",field=models.DecimalField(blank=True,decimal_places=4,max_digits=18,null=True)),
        migrations.AddField(model_name="trip",name="public_price_currency",field=models.ForeignKey(blank=True,null=True,on_delete=django.db.models.deletion.PROTECT,related_name="public_trip_prices",to="reference.currency")),
    ]
