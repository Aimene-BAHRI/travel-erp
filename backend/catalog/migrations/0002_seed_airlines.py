from django.db import migrations


AIRLINES = [
    ("Air Algérie", "AH", "DAH"),
    ("Tassili Airlines", "SF", "DTH"),
    ("Saudia", "SV", "SVA"),
    ("Turkish Airlines", "TK", "THY"),
    ("Emirates", "EK", "UAE"),
    ("Qatar Airways", "QR", "QTR"),
]


def seed_airlines(apps, schema_editor):
    Airline = apps.get_model("catalog", "Airline")
    for name, iata_code, icao_code in AIRLINES:
        Airline.objects.update_or_create(
            iata_code=iata_code,
            defaults={
                "name": name,
                "icao_code": icao_code,
                "is_active": True,
            },
        )


def remove_seeded_airlines(apps, schema_editor):
    Airline = apps.get_model("catalog", "Airline")
    Airline.objects.filter(iata_code__in=[item[1] for item in AIRLINES]).delete()


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [migrations.RunPython(seed_airlines, reverse_code=remove_seeded_airlines)]

