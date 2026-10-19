import uuid
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from bookings.private_storage import passport_storage
from pricing.models import TripHotelPrice


def booking_request_attachment_path(instance, filename):
    return (
        f"agencies/{instance.request.agency_id}/booking-requests/"
        f"{instance.request_id}/{instance.id}/{Path(filename).name}"
    )


class BookingRequest(models.Model):
    class Status(models.TextChoices):
        NEW = "NEW", "New"
        CONTACTED = "CONTACTED", "Contacted"
        QUALIFIED = "QUALIFIED", "Qualified"
        CONVERTED = "CONVERTED", "Converted"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reference = models.CharField(max_length=24, unique=True, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="booking_requests"
    )
    trip = models.ForeignKey(
        "trips.Trip", on_delete=models.PROTECT, related_name="booking_requests"
    )
    customer_name = models.CharField(max_length=180)
    phone = models.CharField(max_length=40)
    email = models.EmailField(blank=True)
    adults = models.PositiveSmallIntegerField(default=1)
    children = models.PositiveSmallIntegerField(default=0)
    children_with_bed = models.PositiveSmallIntegerField(default=0)
    children_without_bed = models.PositiveSmallIntegerField(default=0)
    infants = models.PositiveSmallIntegerField(default=0)
    package = models.ForeignKey(
        "pricing.TripOccupancyPackage",
        on_delete=models.PROTECT,
        related_name="booking_requests",
        null=True,
        blank=True,
    )
    booking = models.OneToOneField(
        "bookings.Booking",
        on_delete=models.SET_NULL,
        related_name="source_booking_request",
        null=True,
        blank=True,
    )
    calculated_total = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    calculated_currency = models.ForeignKey(
        "reference.Currency",
        on_delete=models.PROTECT,
        related_name="public_booking_requests",
        null=True,
        blank=True,
    )
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    preferred_room_type = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    consent = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["agency", "status", "created_at"])]

    def __str__(self):
        return f"{self.reference} - {self.customer_name}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"REQ-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)


class BookingRequestAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        BookingRequest, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(
        upload_to=booking_request_attachment_path, storage=passport_storage, max_length=500
    )
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.original_filename


class Booking(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="bookings"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="bookings"
    )
    code = models.SlugField(max_length=70)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="bookings"
    )
    trip = models.ForeignKey("trips.Trip", on_delete=models.PROTECT, related_name="bookings")
    source_quote = models.OneToOneField(
        "pricing.Quote", on_delete=models.PROTECT, related_name="booking", null=True, blank=True
    )
    partner = models.ForeignKey("partners.Partner", on_delete=models.PROTECT, null=True, blank=True, related_name="bookings")
    commercial_details = models.JSONField(default=dict, blank=True)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="bookings"
    )
    total_amount = models.DecimalField(max_digits=18, decimal_places=4)
    accounting_currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="accounting_bookings"
    )
    accounting_exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=8, default=Decimal("1")
    )
    accounting_total_amount = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)
    notes = models.TextField(blank=True)
    expected_travelers = models.PositiveSmallIntegerField(default=1)
    cancellation_reason = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_bookings"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("view_all_bookings", "Can view all bookings in the agency")]
        constraints = [
            models.UniqueConstraint(fields=["agency", "code"], name="uniq_booking_code_agency"),
            models.CheckConstraint(condition=Q(total_amount__gte=0), name="booking_total_gte_0"),
            models.CheckConstraint(
                condition=Q(accounting_total_amount__gte=0),
                name="booking_accounting_total_gte_0",
            ),
        ]
        indexes = [
            models.Index(fields=["agency", "branch", "status"]),
            models.Index(fields=["agency", "trip", "created_at"]),
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        if self.pk:
            stored = type(self).objects.filter(pk=self.pk).first()
            immutable = [
                "agency_id",
                "branch_id",
                "code",
                "customer_id",
                "trip_id",
                "source_quote_id",
                "partner_id",
                "commercial_details",
                "currency_id",
                "total_amount",
                "accounting_currency_id",
                "accounting_exchange_rate",
                "accounting_total_amount",
                "created_by_id",
            ]
            if (
                stored
                and stored.status != self.Status.DRAFT
                and any(getattr(stored, field) != getattr(self, field) for field in immutable)
            ):
                raise ValidationError("Confirmed booking commercial terms are immutable.")
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        errors = {}
        for field_name in ["branch", "customer", "trip", "partner"]:
            value = getattr(self, field_name, None)
            if value and value.agency_id != self.agency_id:
                errors[field_name] = f"The {field_name} must belong to the same agency."
        if self.source_quote_id:
            if self.source_quote.customer_id != self.customer_id:
                errors["source_quote"] = "The quote customer must match the booking customer."
            if self.source_quote.trip_id != self.trip_id:
                errors["source_quote"] = "The quote trip must match the booking trip."
        if errors:
            raise ValidationError(errors)


class BookingTraveler(models.Model):
    class BedRequirement(models.TextChoices):
        REQUIRED = "REQUIRED", "Bed required"
        NOT_REQUIRED = "NOT_REQUIRED", "No bed required"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="travelers")
    traveler = models.ForeignKey(
        "travelers.Traveler", on_delete=models.PROTECT, related_name="booking_links"
    )
    passenger_category = models.ForeignKey(
        "reference.PassengerCategory", on_delete=models.PROTECT, related_name="booking_travelers"
    )
    bed_requirement = models.CharField(max_length=12, choices=BedRequirement.choices)
    notes = models.TextField(blank=True)
    is_customer_contact = models.BooleanField(default=False)
    seat_required = models.BooleanField(null=True, blank=True)
    service_type = models.CharField(max_length=16, default="PACK", choices=[("PACK", "Full package"), ("VISA_ONLY", "Visa only"), ("TICKET_ONLY", "Ticket only"), ("CUSTOM", "Selected stays")])
    included_stops = models.ManyToManyField("trips.TripStop", blank=True, related_name="included_travelers")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["added_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "traveler"], name="uniq_traveler_per_booking"
            ),
            models.UniqueConstraint(
                fields=["booking"],
                condition=Q(is_customer_contact=True),
                name="uniq_customer_contact_traveler_per_booking",
            ),
        ]

    def __str__(self):
        return f"{self.booking.code}: {self.traveler_id}"

    def clean(self):
        super().clean()
        errors = {}
        if self.traveler_id and self.traveler.agency_id != self.booking.agency_id:
            errors["traveler"] = "The traveler must belong to the booking agency."
        if self.passenger_category_id:
            category_agency = self.passenger_category.agency_id
            if category_agency and category_agency != self.booking.agency_id:
                errors["passenger_category"] = "The passenger category is unavailable."
        if errors:
            raise ValidationError(errors)


class BookingAccommodation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="accommodations")
    trip_hotel = models.ForeignKey(
        "trips.TripHotel", on_delete=models.PROTECT, related_name="booking_accommodations"
    )
    room_type = models.ForeignKey(
        "catalog.RoomType", on_delete=models.PROTECT, related_name="booking_accommodations"
    )
    passenger_category = models.ForeignKey(
        "reference.PassengerCategory",
        on_delete=models.PROTECT,
        related_name="booking_accommodations",
    )
    bed_basis = models.CharField(max_length=12, choices=TripHotelPrice.BedBasis.choices)
    quantity = models.PositiveIntegerField()
    unit_amount = models.DecimalField(max_digits=18, decimal_places=4)
    total_amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="booking_accommodations"
    )
    source_quote_line = models.OneToOneField(
        "pricing.QuoteLine",
        on_delete=models.PROTECT,
        related_name="booking_accommodation",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["trip_hotel__stop__order", "room_type__sort_order", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gte=1), name="booking_accommodation_quantity_gte_1"
            ),
            models.CheckConstraint(
                condition=Q(unit_amount__gte=0), name="booking_accommodation_unit_gte_0"
            ),
            models.CheckConstraint(
                condition=Q(total_amount__gte=0), name="booking_accommodation_total_gte_0"
            ),
        ]

    def __str__(self):
        return f"{self.booking.code}: {self.trip_hotel.hotel.name} {self.room_type.name}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Sold accommodation is immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Sold accommodation cannot be deleted.")


class BookingFlight(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="flights")
    trip_flight = models.ForeignKey(
        "trips.TripFlight", on_delete=models.PROTECT, related_name="booking_selections"
    )

    class Meta:
        ordering = ["trip_flight__order"]
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "trip_flight"], name="uniq_trip_flight_per_booking"
            )
        ]

    def __str__(self):
        return f"{self.booking.code}: {self.trip_flight.flight_number}"


class BookingSnapshot(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.PROTECT, related_name="snapshot")
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Snapshot {self.booking.code}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Booking snapshots are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Booking snapshots cannot be deleted.")


class BookingRoomGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="room_groups")
    trip_hotel = models.ForeignKey(
        "trips.TripHotel", on_delete=models.PROTECT, related_name="booking_room_groups"
    )
    room_type = models.ForeignKey(
        "catalog.RoomType", on_delete=models.PROTECT, related_name="booking_room_groups"
    )
    label = models.CharField(max_length=80)
    capacity = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["trip_hotel__stop__order", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["booking", "trip_hotel", "label"], name="uniq_booking_room_label"
            ),
            models.CheckConstraint(
                condition=Q(capacity__gte=1), name="booking_room_capacity_gte_1"
            ),
        ]

    def __str__(self):
        return f"{self.booking.code} - {self.label}"


class BookingRoomTraveler(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_group = models.ForeignKey(
        BookingRoomGroup, on_delete=models.CASCADE, related_name="traveler_assignments"
    )
    booking_traveler = models.ForeignKey(
        BookingTraveler, on_delete=models.CASCADE, related_name="room_assignments"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["room_group", "booking_traveler"], name="uniq_traveler_per_room_group"
            )
        ]

    def __str__(self):
        return f"{self.room_group} - {self.booking_traveler}"


class BookingTravelerCharge(models.Model):
    class Kind(models.TextChoices):
        ACCOMMODATION = "ACCOMMODATION", "Accommodation"
        TRANSPORT = "TRANSPORT", "Transport"
        VISA = "VISA", "Visa"
        SERVICE = "SERVICE", "Service"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_traveler = models.ForeignKey(
        BookingTraveler, on_delete=models.CASCADE, related_name="charges"
    )
    kind = models.CharField(max_length=16, choices=Kind.choices)
    description = models.CharField(max_length=180)
    source_price = models.ForeignKey(
        "pricing.TripHotelPrice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="booking_traveler_charges",
    )
    base_amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="booking_traveler_charges"
    )
    pricing_snapshot = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.booking_traveler} - {self.description}"

    @property
    def discount_amount(self):
        total = Decimal("0")
        for discount in self.discounts.all():
            total += (
                discount.amount
                if discount.kind == BookingDiscount.Kind.AMOUNT
                else (self.base_amount * discount.value / Decimal("100"))
            )
        return min(total, self.base_amount)

    @property
    def final_amount(self):
        return self.base_amount - self.discount_amount


class BookingDiscount(models.Model):
    class Kind(models.TextChoices):
        AMOUNT = "AMOUNT", "Fixed amount"
        PERCENT = "PERCENT", "Percentage"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    charge = models.ForeignKey(
        BookingTravelerCharge, on_delete=models.CASCADE, related_name="discounts"
    )
    kind = models.CharField(max_length=8, choices=Kind.choices)
    value = models.DecimalField(max_digits=18, decimal_places=4)
    amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    reason = models.CharField(max_length=240)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="authorized_discounts"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(value__gt=0), name="booking_discount_value_gt_0")
        ]

    def __str__(self):
        return f"{self.kind} {self.value} - {self.reason}"
