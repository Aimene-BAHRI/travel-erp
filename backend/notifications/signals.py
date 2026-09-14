from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from bookings.models import Booking
from finance.models import FinancialTransaction
from trips.models import TripFlight, TripStop, TripTransport

from .models import NotificationRule
from .services import notify_agency


@receiver(post_save, sender=FinancialTransaction)
def payment_notification(sender, instance, created, **kwargs):
    if created and instance.kind == FinancialTransaction.Kind.PAYMENT:
        notify_agency(
            agency=instance.agency,
            branch=instance.branch,
            event=NotificationRule.Event.PAYMENT_RECEIVED,
            title="Customer payment received",
            message=f"{instance.booking.code}: {instance.amount} {instance.currency_id} received.",
            target_url=f"/bookings/{instance.booking_id}",
            dedupe_key=f"PAYMENT_RECEIVED:{instance.pk}",
        )


@receiver(post_save, sender=Booking)
def booking_notification(sender, instance, created, **kwargs):
    if created:
        event, title = NotificationRule.Event.BOOKING_CREATED, "Booking created"
    elif instance.status == Booking.Status.CANCELLED:
        event, title = NotificationRule.Event.BOOKING_CANCELLED, "Booking cancelled"
    else:
        return
    notify_agency(
        agency=instance.agency,
        branch=instance.branch,
        event=event,
        title=title,
        message=f"{instance.code} · {instance.customer.display_name}",
        target_url=f"/bookings/{instance.pk}",
        dedupe_key=f"{event}:{instance.pk}",
    )


@receiver(post_save, sender=TripStop)
@receiver(post_save, sender=TripFlight)
@receiver(post_save, sender=TripTransport)
def trip_change_notification(sender, instance, created, **kwargs):
    if created:
        return
    trip = instance.trip
    notify_agency(
        agency=trip.agency,
        branch=trip.branch,
        event=NotificationRule.Event.TRIP_CHANGED,
        title="Trip itinerary changed",
        message=f"Operational details changed for {trip.name}.",
        target_url=f"/trips/{trip.pk}",
        dedupe_key=f"TRIP_CHANGED:{sender.__name__}:{instance.pk}:{timezone.now().isoformat()}",
    )
