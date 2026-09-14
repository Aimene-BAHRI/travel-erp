from django.db import migrations


TABLE = "bookings_booking"
COLUMN = "amendment_reason"


def _column_names(schema_editor):
    with schema_editor.connection.cursor() as cursor:
        description = schema_editor.connection.introspection.get_table_description(cursor, TABLE)
    return {column.name for column in description}


def remove_legacy_column(apps, schema_editor):
    if COLUMN in _column_names(schema_editor):
        schema_editor.execute(f'ALTER TABLE "{TABLE}" DROP COLUMN "{COLUMN}"')


def restore_legacy_column(apps, schema_editor):
    if COLUMN not in _column_names(schema_editor):
        schema_editor.execute(
            f'ALTER TABLE "{TABLE}" ADD COLUMN "{COLUMN}" text NOT NULL DEFAULT \'\''
        )


class Migration(migrations.Migration):
    dependencies = [
        ("bookings", "0005_bookingtraveler_is_customer_contact_and_more"),
    ]

    operations = [
        migrations.RunPython(remove_legacy_column, restore_legacy_column),
    ]
