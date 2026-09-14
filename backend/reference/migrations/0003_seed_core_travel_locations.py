from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("reference", "0002_seed_financial_reference_data")]
    # Locations are deployment-managed reference data. Keeping this migration
    # empty avoids polluting isolated databases and lets installations choose
    # the geographic catalogue they support.
    operations = []
