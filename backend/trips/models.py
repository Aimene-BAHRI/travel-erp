import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Trip(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        OPEN = "OPEN", "Open for booking"
        CLOSED = "CLOSED", "Closed for booking"
        DEPARTED = "DEPARTED", "Departed"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    class ClosingStatus(models.TextChoices):
        NOT_DUE = "NOT_DUE", "Not due"
        PENDING = "PENDING_CLOSING", "Pending closing"
        READY = "READY_TO_CLOSE", "Ready to close"
        CLOSED = "CLOSED", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="trips"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="trips"
    )
    code = models.SlugField(max_length=60)
    name = models.CharField(max_length=180)
    departure_date = models.DateField()
    return_date = models.DateField()
    pricing_currency = models.ForeignKey(
        "reference.Currency",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="priced_trips",
    )
    child_with_bed_discount = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    child_without_bed_price = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    infant_price = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    booking_open_date = models.DateField(null=True, blank=True)
    booking_close_date = models.DateField(null=True, blank=True)
    max_travelers = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    closing_status = models.CharField(
        max_length=16, choices=ClosingStatus.choices, default=ClosingStatus.NOT_DUE
    )
    closing_started_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="closed_trips",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_trips",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-departure_date", "name"]
        permissions = [
            ("view_all_trips", "Can view all trips in the agency"),
            ("close_trip", "Can complete and reopen trip closing"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["agency", "code"], name="uniq_trip_code_agency"),
            models.CheckConstraint(
                condition=Q(return_date__gte=F("departure_date")),
                name="trip_return_on_or_after_departure",
            ),
            models.CheckConstraint(
                condition=Q(booking_open_date__isnull=True)
                | Q(booking_close_date__isnull=True)
                | Q(booking_close_date__gte=F("booking_open_date")),
                name="trip_booking_window_order",
            ),
            models.CheckConstraint(
                condition=Q(booking_close_date__isnull=True)
                | Q(booking_close_date__lte=F("departure_date")),
                name="trip_booking_closes_by_departure",
            ),
            models.CheckConstraint(
                condition=Q(child_with_bed_discount__isnull=True)
                | Q(child_with_bed_discount__gte=0),
                name="trip_child_bed_discount_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(child_without_bed_price__isnull=True)
                | Q(child_without_bed_price__gte=0),
                name="trip_child_no_bed_price_gte_0",
            ),
            models.CheckConstraint(
                condition=Q(infant_price__isnull=True) | Q(infant_price__gte=0),
                name="trip_infant_price_gte_0",
            ),
        ]
        indexes = [
            models.Index(fields=["agency", "branch", "status"]),
            models.Index(fields=["agency", "departure_date"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        super().clean()
        errors = {}
        if self.branch_id and self.agency_id and self.branch.agency_id != self.agency_id:
            errors["branch"] = "The branch must belong to the same agency."
        if self.return_date and self.departure_date and self.return_date < self.departure_date:
            errors["return_date"] = "Return date cannot precede departure date."
        if (
            self.booking_open_date
            and self.booking_close_date
            and self.booking_close_date < self.booking_open_date
        ):
            errors["booking_close_date"] = "Booking close date cannot precede opening."
        if (
            self.booking_close_date
            and self.departure_date
            and self.booking_close_date > self.departure_date
        ):
            errors["booking_close_date"] = "Bookings must close by departure."
        if errors:
            raise ValidationError(errors)


class TripStop(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="stops")
    city = models.ForeignKey("reference.City", on_delete=models.PROTECT, related_name="trip_stops")
    arrival_date = models.DateField()
    departure_date = models.DateField()
    order = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "arrival_date"]
        constraints = [
            models.UniqueConstraint(fields=["trip", "order"], name="uniq_trip_stop_order"),
            models.CheckConstraint(
                condition=Q(departure_date__gte=F("arrival_date")),
                name="trip_stop_departure_on_or_after_arrival",
            ),
        ]
        indexes = [models.Index(fields=["trip", "order"])]

    def __str__(self):
        return f"{self.trip.code} #{self.order}: {self.city.name}"

    @property
    def nights(self):
        return (self.departure_date - self.arrival_date).days

    def clean(self):
        super().clean()
        errors = {}
        if self.arrival_date and self.arrival_date < self.trip.departure_date:
            errors["arrival_date"] = "A stop cannot begin before trip departure."
        if self.departure_date and self.departure_date > self.trip.return_date:
            errors["departure_date"] = "A stop cannot end after trip return."
        if self.departure_date and self.arrival_date and self.departure_date < self.arrival_date:
            errors["departure_date"] = "Stop departure cannot precede arrival."
        if errors:
            raise ValidationError(errors)


class TripHotel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stop = models.ForeignKey(TripStop, on_delete=models.CASCADE, related_name="hotels")
    hotel = models.ForeignKey("catalog.Hotel", on_delete=models.PROTECT, related_name="trip_uses")
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["stop__order", "hotel__name"]
        constraints = [
            models.UniqueConstraint(fields=["stop", "hotel"], name="uniq_hotel_per_trip_stop"),
            models.UniqueConstraint(
                fields=["stop"], condition=Q(is_primary=True), name="uniq_primary_hotel_trip_stop"
            ),
        ]

    def __str__(self):
        return f"{self.stop}: {self.hotel.name}"

    def clean(self):
        super().clean()
        errors = {}
        if self.hotel_id and self.stop_id:
            if self.hotel.agency_id != self.stop.trip.agency_id:
                errors["hotel"] = "The hotel must belong to the trip agency."
            if self.hotel.city_id != self.stop.city_id:
                errors["hotel"] = "The hotel must be located in the stop city."
        if errors:
            raise ValidationError(errors)


class TripAllocationRoom(models.Model):
    class OccupancyPolicy(models.TextChoices):
        ANY = "ANY", "Any travelers"
        MALE_ONLY = "MALE_ONLY", "Male only"
        FEMALE_ONLY = "FEMALE_ONLY", "Female only"
        FAMILY = "FAMILY", "Family / approved mixed group"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip_hotel = models.ForeignKey(
        TripHotel, on_delete=models.CASCADE, related_name="allocation_rooms"
    )
    room_type = models.ForeignKey(
        "catalog.RoomType", on_delete=models.PROTECT, related_name="trip_allocation_rooms"
    )
    label = models.CharField(max_length=80)
    actual_room_number = models.CharField(max_length=30, blank=True)
    standard_beds = models.PositiveSmallIntegerField()
    extra_beds = models.PositiveSmallIntegerField(default=0)
    occupancy_policy = models.CharField(
        max_length=12, choices=OccupancyPolicy.choices, default=OccupancyPolicy.ANY
    )
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_trip_allocation_rooms",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trip_hotel__stop__order", "trip_hotel__hotel__name", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip_hotel", "label"], name="uniq_allocation_room_label_hotel"
            ),
            models.CheckConstraint(
                condition=Q(standard_beds__gte=1), name="allocation_room_standard_beds_gte_1"
            ),
        ]

    def __str__(self):
        return f"{self.trip_hotel.hotel.name} - {self.label}"

    @property
    def capacity(self):
        return self.standard_beds + self.extra_beds

    def clean(self):
        super().clean()
        if (
            self.trip_hotel_id
            and self.room_type_id
            and self.room_type.agency_id != self.trip_hotel.stop.trip.agency_id
        ):
            raise ValidationError({"room_type": "Room type must belong to the trip agency."})


class TripRoomAssignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stop = models.ForeignKey(TripStop, on_delete=models.CASCADE, related_name="room_assignments")
    room = models.ForeignKey(
        TripAllocationRoom, on_delete=models.PROTECT, related_name="assignments"
    )
    booking_traveler = models.ForeignKey(
        "bookings.BookingTraveler",
        on_delete=models.PROTECT,
        related_name="trip_room_assignments",
    )
    bed_number = models.PositiveSmallIntegerField()
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="trip_room_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["stop__order", "room__label", "bed_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["stop", "booking_traveler"],
                name="uniq_trip_stop_room_assignment_traveler",
            ),
            models.UniqueConstraint(
                fields=["room", "bed_number"], name="uniq_allocation_room_bed_number"
            ),
            models.CheckConstraint(
                condition=Q(bed_number__gte=1), name="room_assignment_bed_number_gte_1"
            ),
        ]

    def __str__(self):
        return f"{self.booking_traveler} - {self.room} / {self.bed_number}"

    def clean(self):
        super().clean()
        errors = {}
        if self.room_id and self.stop_id and self.room.trip_hotel.stop_id != self.stop_id:
            errors["room"] = "Room must belong to the selected itinerary stop."
        if self.room_id and self.bed_number and self.bed_number > self.room.capacity:
            errors["bed_number"] = "Bed number exceeds the room capacity."
        if self.booking_traveler_id and self.stop_id:
            booking = self.booking_traveler.booking
            if booking.trip_id != self.stop.trip_id:
                errors["booking_traveler"] = "Traveler must belong to this trip."
            if booking.status not in {"DRAFT", "CONFIRMED", "COMPLETED"}:
                errors["booking_traveler"] = "Only active booking travelers can be allocated."
        if self.room_id and self.booking_traveler_id:
            gender = self.booking_traveler.traveler.gender
            if (
                self.room.occupancy_policy == TripAllocationRoom.OccupancyPolicy.MALE_ONLY
                and gender != "M"
            ):
                errors["booking_traveler"] = "Only male travelers may use this room."
            if (
                self.room.occupancy_policy == TripAllocationRoom.OccupancyPolicy.FEMALE_ONLY
                and gender != "F"
            ):
                errors["booking_traveler"] = "Only female travelers may use this room."
        if errors:
            raise ValidationError(errors)


class TripFlight(models.Model):
    class Direction(models.TextChoices):
        OUTBOUND = "OUTBOUND", "Outbound"
        RETURN = "RETURN", "Return"
        INTERNAL = "INTERNAL", "Internal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="flights")
    airline = models.ForeignKey(
        "catalog.Airline", on_delete=models.PROTECT, related_name="trip_flights"
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    flight_number = models.CharField(max_length=20)
    origin_city = models.ForeignKey(
        "reference.City", on_delete=models.PROTECT, related_name="departing_trip_flights"
    )
    destination_city = models.ForeignKey(
        "reference.City", on_delete=models.PROTECT, related_name="arriving_trip_flights"
    )
    origin_airport_code = models.CharField(max_length=3)
    destination_airport_code = models.CharField(max_length=3)
    departure_at = models.DateTimeField()
    arrival_at = models.DateTimeField()
    booking_class = models.CharField(max_length=20, blank=True)
    order = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "departure_at"]
        constraints = [
            models.UniqueConstraint(fields=["trip", "order"], name="uniq_trip_flight_order"),
            models.CheckConstraint(
                condition=Q(arrival_at__gt=F("departure_at")),
                name="trip_flight_arrival_after_departure",
            ),
        ]
        indexes = [models.Index(fields=["trip", "order"])]

    def __str__(self):
        return f"{self.flight_number}: {self.origin_airport_code}-{self.destination_airport_code}"

    def save(self, *args, **kwargs):
        self.flight_number = self.flight_number.upper().replace(" ", "")
        self.origin_airport_code = self.origin_airport_code.upper()
        self.destination_airport_code = self.destination_airport_code.upper()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.arrival_at and self.departure_at and self.arrival_at <= self.departure_at:
            raise ValidationError({"arrival_at": "Arrival must be after departure."})
        if self.origin_city_id and self.origin_city_id == self.destination_city_id:
            raise ValidationError({"destination_city": "Flight cities must be different."})


class TripTransport(models.Model):
    class Mode(models.TextChoices):
        BUS = "BUS", "Bus"
        PRIVATE_CAR = "PRIVATE_CAR", "Private car"
        TRAIN = "TRAIN", "Train"
        FERRY = "FERRY", "Ferry"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="transports")
    mode = models.CharField(max_length=12, choices=Mode.choices)
    supplier = models.ForeignKey(
        "catalog.Supplier",
        on_delete=models.PROTECT,
        related_name="trip_transports",
        null=True,
        blank=True,
    )
    origin_city = models.ForeignKey(
        "reference.City", on_delete=models.PROTECT, related_name="departing_trip_transports"
    )
    destination_city = models.ForeignKey(
        "reference.City", on_delete=models.PROTECT, related_name="arriving_trip_transports"
    )
    departure_at = models.DateTimeField()
    arrival_at = models.DateTimeField()
    reference = models.CharField(max_length=120, blank=True)
    vehicle_details = models.CharField(max_length=180, blank=True)
    vehicle_number = models.CharField(max_length=40, blank=True)
    order = models.PositiveSmallIntegerField()
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["order", "departure_at"]
        constraints = [
            models.UniqueConstraint(fields=["trip", "order"], name="uniq_trip_transport_order"),
            models.CheckConstraint(
                condition=Q(arrival_at__gt=F("departure_at")),
                name="trip_transport_arrival_after_departure",
            ),
        ]
        indexes = [models.Index(fields=["trip", "order"])]

    def __str__(self):
        return f"{self.get_mode_display()}: {self.origin_city} - {self.destination_city}"

    def clean(self):
        super().clean()
        errors = {}
        if self.arrival_at and self.departure_at and self.arrival_at <= self.departure_at:
            errors["arrival_at"] = "Arrival must be after departure."
        if self.origin_city_id and self.origin_city_id == self.destination_city_id:
            errors["destination_city"] = "Transport cities must be different."
        if self.supplier_id and self.supplier.agency_id != self.trip.agency_id:
            errors["supplier"] = "The supplier must belong to the trip agency."
        if errors:
            raise ValidationError(errors)


class TripDocument(models.Model):
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="document_links")
    document = models.OneToOneField(
        "documents.Document", on_delete=models.CASCADE, related_name="trip_link"
    )
    purpose = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"{self.trip.code}: {self.document.title}"


class TripClosingItem(models.Model):
    class Key(models.TextChoices):
        TRAVELERS_RETURNED = "TRAVELERS_RETURNED", "Travelers returned / exceptions settled"
        FLIGHT_FILE = "FLIGHT_FILE", "Flight file closed"
        HOTEL_ACCOUNT = "HOTEL_ACCOUNT", "Hotel account closed"
        TRANSPORT_ACCOUNT = "TRANSPORT_ACCOUNT", "Transport account closed"
        SUPPLIER_SETTLEMENTS = "SUPPLIER_SETTLEMENTS", "Supplier dues settled / recorded"
        CUSTOMER_SETTLEMENTS = "CUSTOMER_SETTLEMENTS", "Customer dues settled / recorded"
        GUIDE_ADVANCE = "GUIDE_ADVANCE", "Guide advance settled"
        COMPLAINTS = "COMPLAINTS", "Complaints resolved"
        PROFIT_LOSS = "PROFIT_LOSS", "Profit and loss calculated"
        DOCUMENTS_ARCHIVED = "DOCUMENTS_ARCHIVED", "Documents archived"
        FINAL_REPORT = "FINAL_REPORT", "Final trip report"

    class State(models.TextChoices):
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        NOT_REQUIRED = "NOT_REQUIRED", "Not required"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="closing_items")
    key = models.CharField(max_length=30, choices=Key.choices)
    state = models.CharField(max_length=12, choices=State.choices, default=State.PENDING)
    notes = models.TextField(blank=True)
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="assigned_trip_closing_items",
    )
    due_date = models.DateField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="completed_trip_closing_items",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]
        constraints = [
            models.UniqueConstraint(fields=["trip", "key"], name="uniq_trip_closing_item")
        ]

    def __str__(self):
        return f"{self.trip.code}: {self.get_key_display()}"
