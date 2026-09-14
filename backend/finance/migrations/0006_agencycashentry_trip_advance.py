from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("finance", "0005_rename_finance_age_agency__f7f6c7_idx_finance_age_agency__2bfdaf_idx_and_more")]

    operations = [
        migrations.AddField(
            model_name="agencycashentry",
            name="exchange_rate",
            field=models.DecimalField(blank=True, decimal_places=8, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="agencycashentry",
            name="recipient_name",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="agencycashentry",
            name="source_amount",
            field=models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True),
        ),
        migrations.AddField(
            model_name="agencycashentry",
            name="source_currency",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.PROTECT, related_name="source_agency_cash_entries", to="reference.currency"),
        ),
        migrations.AddConstraint(
            model_name="agencycashentry",
            constraint=models.CheckConstraint(condition=models.Q(("source_amount__isnull", True)) | models.Q(("source_amount__gt", 0)), name="agency_cash_source_amount_gt_0"),
        ),
        migrations.AddConstraint(
            model_name="agencycashentry",
            constraint=models.CheckConstraint(condition=models.Q(("exchange_rate__isnull", True)) | models.Q(("exchange_rate__gt", 0)), name="agency_cash_exchange_rate_gt_0"),
        ),
    ]