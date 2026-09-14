from django.db import migrations


CURRENCIES = [
    ("DZD", "Algerian Dinar", "DA", 2),
    ("EUR", "Euro", "€", 2),
    ("SAR", "Saudi Riyal", "﷼", 2),
    ("USD", "US Dollar", "$", 2),
]

PASSENGER_CATEGORIES = [
    ("adt", "Adult", True, 10),
    ("chd", "Child", True, 20),
    ("inf", "Infant", False, 30),
    ("guide", "Guide", True, 40),
]

PAYMENT_METHODS = [
    ("cash", "Cash", 10),
    ("bank-transfer", "Bank Transfer", 20),
    ("card", "Payment Card", 30),
    ("cheque", "Cheque", 40),
]


def seed_reference_data(apps, schema_editor):
    Agency = apps.get_model("organizations", "Agency")
    AgencyCurrency = apps.get_model("reference", "AgencyCurrency")
    Currency = apps.get_model("reference", "Currency")
    PassengerCategory = apps.get_model("reference", "PassengerCategory")
    PaymentMethod = apps.get_model("reference", "PaymentMethod")

    currencies = {}
    for code, name, symbol, decimal_places in CURRENCIES:
        currencies[code], _ = Currency.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "symbol": symbol,
                "decimal_places": decimal_places,
                "is_active": True,
            },
        )

    for code, name, requires_bed, sort_order in PASSENGER_CATEGORIES:
        PassengerCategory.objects.update_or_create(
            code=code,
            is_system=True,
            defaults={
                "agency": None,
                "name": name,
                "requires_bed_by_default": requires_bed,
                "is_active": True,
                "sort_order": sort_order,
            },
        )

    for code, name, sort_order in PAYMENT_METHODS:
        PaymentMethod.objects.update_or_create(
            code=code,
            is_system=True,
            defaults={
                "agency": None,
                "name": name,
                "is_active": True,
                "sort_order": sort_order,
            },
        )

    for agency in Agency.objects.all():
        for code, currency in currencies.items():
            AgencyCurrency.objects.get_or_create(
                agency=agency,
                currency=currency,
                defaults={"is_enabled": True, "is_accounting": code == "DZD"},
            )


def remove_seeded_reference_data(apps, schema_editor):
    AgencyCurrency = apps.get_model("reference", "AgencyCurrency")
    Currency = apps.get_model("reference", "Currency")
    PassengerCategory = apps.get_model("reference", "PassengerCategory")
    PaymentMethod = apps.get_model("reference", "PaymentMethod")

    AgencyCurrency.objects.filter(currency_id__in=[item[0] for item in CURRENCIES]).delete()
    PassengerCategory.objects.filter(
        is_system=True, code__in=[item[0] for item in PASSENGER_CATEGORIES]
    ).delete()
    PaymentMethod.objects.filter(
        is_system=True, code__in=[item[0] for item in PAYMENT_METHODS]
    ).delete()
    Currency.objects.filter(code__in=[item[0] for item in CURRENCIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("reference", "0001_initial")]

    operations = [
        migrations.RunPython(seed_reference_data, reverse_code=remove_seeded_reference_data)
    ]

