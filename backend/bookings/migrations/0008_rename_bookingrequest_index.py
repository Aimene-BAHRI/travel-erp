from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("bookings", "0007_bookingrequest")]

    operations = [
        migrations.RenameIndex(
            model_name="bookingrequest",
            old_name="bookings_bo_agency__e3df18_idx",
            new_name="bookings_bo_agency__81926a_idx",
        ),
    ]
