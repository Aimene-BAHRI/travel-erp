from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("partners", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="partnerallocation",
            name="reserved_quantity",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
