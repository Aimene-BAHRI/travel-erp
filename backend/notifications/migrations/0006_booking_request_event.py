from django.db import migrations, models


EVENTS = [("TRIP_DEPARTURE", "Trip departure approaching"), ("TRIP_CLOSING", "Trip pending closing"), ("BOOKING_BALANCE", "Booking balance before departure"), ("SUPPLIER_DUE", "Supplier expense due"), ("PAYMENT_RECEIVED", "Customer payment received"), ("PASSPORT_ATTENTION", "Passport missing or expiring"), ("ROOM_ALLOCATION", "Room allocation incomplete"), ("CLOSING_OVERDUE", "Trip closing task overdue"), ("BOOKING_CREATED", "Booking created"), ("BOOKING_CANCELLED", "Booking cancelled"), ("TRIP_CHANGED", "Trip itinerary changed"), ("BOOKING_REQUEST", "New public booking request")]


class Migration(migrations.Migration):
    dependencies = [("notifications", "0005_alter_notification_event_and_more")]
    operations = [
        migrations.AlterField(model_name="notification", name="event", field=models.CharField(choices=EVENTS, max_length=30)),
        migrations.AlterField(model_name="notificationrule", name="event", field=models.CharField(choices=EVENTS, max_length=30)),
    ]
