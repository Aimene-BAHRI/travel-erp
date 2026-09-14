import uuid

from django.conf import settings
from django.db import models


class NotificationRule(models.Model):
    class Event(models.TextChoices):
        READINESS = "READINESS", "Trip readiness summary"
        TRIP_DEPARTURE = "TRIP_DEPARTURE", "Trip departure approaching"
        TRIP_CLOSING = "TRIP_CLOSING", "Trip pending closing"
        BOOKING_BALANCE = "BOOKING_BALANCE", "Booking balance before departure"
        SUPPLIER_DUE = "SUPPLIER_DUE", "Supplier expense due"
        PAYMENT_RECEIVED = "PAYMENT_RECEIVED", "Customer payment received"
        PASSPORT_ATTENTION = "PASSPORT_ATTENTION", "Passport missing or expiring"
        ROOM_ALLOCATION = "ROOM_ALLOCATION", "Room allocation incomplete"
        CLOSING_OVERDUE = "CLOSING_OVERDUE", "Trip closing task overdue"
        BOOKING_CREATED = "BOOKING_CREATED", "Booking created"
        BOOKING_CANCELLED = "BOOKING_CANCELLED", "Booking cancelled"
        TRIP_CHANGED = "TRIP_CHANGED", "Trip itinerary changed"
        BOOKING_REQUEST = "BOOKING_REQUEST", "New public booking request"
        TRANSPORT_DETAILS = "TRANSPORT_DETAILS", "Ground transport details incomplete"

    agency = models.ForeignKey("organizations.Agency", on_delete=models.CASCADE)
    event = models.CharField(max_length=30, choices=Event.choices)
    is_enabled = models.BooleanField(default=True)
    lead_days = models.PositiveSmallIntegerField(default=3)
    branch_only = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["agency", "event"], name="uniq_notification_rule")
        ]

    def __str__(self):
        return f"{self.agency}: {self.get_event_display()}"


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey("organizations.Agency", on_delete=models.CASCADE)
    branch = models.ForeignKey("organizations.Branch", on_delete=models.CASCADE, null=True)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    event = models.CharField(max_length=30, choices=NotificationRule.Event.choices)
    severity = models.CharField(max_length=10, choices=[("SUCCESS", "Success"), ("INFO", "Information"), ("WARNING", "Warning"), ("ERROR", "Error")], default="INFO")
    title = models.CharField(max_length=180)
    message = models.TextField()
    target_url = models.CharField(max_length=240)
    dedupe_key = models.CharField(max_length=240)
    read_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "dedupe_key"], name="uniq_recipient_notification"
            )
        ]

    def __str__(self):
        return f"{self.recipient}: {self.title}"
