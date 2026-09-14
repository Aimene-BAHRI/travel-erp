from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0006_agencycashentry_trip_advance")]

    operations = [
        migrations.AlterField(
            model_name="agencycashentry",
            name="category",
            field=models.CharField(
                choices=[
                    ("OTHER_INCOME", "Other income"),
                    ("OWNER_FUNDS", "Owner funds"),
                    ("OPERATING_COST", "Operating cost"),
                    ("TAX", "Tax"),
                    ("SALARY", "Salary"),
                    ("TRANSFER", "Transfer"),
                    ("TRIP_ADVANCE", "Trip advance"),
                    ("OTHER_EXPENSE", "Other expense"),
                ],
                max_length=20,
            ),
        ),
    ]