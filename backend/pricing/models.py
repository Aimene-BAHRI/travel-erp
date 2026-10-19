import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class TripCostComponent(models.Model):
    class Basis(models.TextChoices):
        PER_TRAVELER = "PER_TRAVELER", "Per traveler"
        MAKKAH_ROOM = "MAKKAH_ROOM", "Makkah room/stay"
        MADINAH_ROOM = "MADINAH_ROOM", "Madinah room/stay"

    class AppliesTo(models.TextChoices):
        ALL = "ALL", "All travelers"
        ADULT = "ADULT", "Adult"
        CHILD_BED = "CHILD_BED", "Child with bed"
        CHILD_NO_BED = "CHILD_NO_BED", "Child without bed"
        INFANT = "INFANT", "Infant"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="trip_cost_components"
    )
    trip = models.ForeignKey("trips.Trip", on_delete=models.CASCADE, related_name="cost_components")
    code = models.SlugField(max_length=40)
    label = models.CharField(max_length=100)
    basis = models.CharField(max_length=20, choices=Basis.choices, default=Basis.PER_TRAVELER)
    applies_to = models.CharField(max_length=20, choices=AppliesTo.choices, default=AppliesTo.ALL)
    source_amount = models.DecimalField(max_digits=18, decimal_places=4)
    source_currency = models.ForeignKey("reference.Currency", on_delete=models.PROTECT)
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal("1"))
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1"))
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code", "applies_to"]
        constraints = [
            models.UniqueConstraint(
                fields=["trip", "code", "applies_to"], name="uniq_trip_cost_component"
            ),
            models.CheckConstraint(condition=Q(source_amount__gte=0), name="cost_amount_gte_0"),
            models.CheckConstraint(condition=Q(exchange_rate__gt=0), name="cost_rate_gt_0"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="cost_quantity_gt_0"),
        ]

    def __str__(self):
        return self.label

    @property
    def converted_amount(self):
        return self.source_amount * self.exchange_rate * self.quantity

    def clean(self):
        super().clean()
        if self.trip_id and self.trip.agency_id != self.agency_id:
            raise ValidationError({"trip": "The trip must belong to the same agency."})


class TripOccupancyPackage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="trip_packages"
    )
    trip = models.ForeignKey(
        "trips.Trip", on_delete=models.CASCADE, related_name="occupancy_packages"
    )
    code = models.SlugField(max_length=30)
    name = models.CharField(max_length=80)
    adult_price = models.ForeignKey("pricing.TripHotelPrice", on_delete=models.PROTECT, null=True, blank=True, related_name="sale_packages")
    makkah_occupancy = models.PositiveSmallIntegerField(default=1)
    madinah_occupancy = models.PositiveSmallIntegerField(default=1)
    margin_adult = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    margin_child_bed = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    margin_child_no_bed = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    margin_infant = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    override_adult = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    override_child_bed = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    override_child_no_bed = models.DecimalField(
        max_digits=18, decimal_places=4, null=True, blank=True
    )
    override_infant = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    rounding_increment = models.PositiveIntegerField(default=100)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["makkah_occupancy", "name"]
        constraints = [
            models.UniqueConstraint(fields=["trip", "code"], name="uniq_trip_occupancy_package"),
            models.CheckConstraint(
                condition=Q(makkah_occupancy__gte=1), name="package_makkah_occupancy_gte_1"
            ),
            models.CheckConstraint(
                condition=Q(madinah_occupancy__gte=1), name="package_madinah_occupancy_gte_1"
            ),
            models.CheckConstraint(
                condition=Q(rounding_increment__gte=1), name="package_rounding_gte_1"
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.trip_id and self.trip.agency_id != self.agency_id:
            raise ValidationError({"trip": "The trip must belong to the same agency."})
        for category in ("adult", "child_bed", "child_no_bed", "infant"):
            value = getattr(self, f"override_{category}")
            if value is not None and value < 0:
                raise ValidationError({f"override_{category}": "Price cannot be negative."})
        if self.adult_price_id:
            price = self.adult_price
            if price.trip_hotel.stop.trip_id != self.trip_id or price.scope != "TRIP_PACKAGE" or price.passenger_category.code.upper() != "ADT" or price.price_kind != "STANDARD":
                raise ValidationError({"adult_price": "Select a standard adult whole-trip price from this trip."})
        if self.is_published:
            from pricing.calculator import calculate_package

            calculate_package(self)


class TripHotelFixedPrice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="trip_hotel_fixed_prices"
    )
    trip_hotel = models.OneToOneField(
        "trips.TripHotel", on_delete=models.CASCADE, related_name="fixed_prices"
    )
    child_without_bed = models.DecimalField(max_digits=18, decimal_places=4)
    infant = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="trip_hotel_fixed_prices"
    )

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(child_without_bed__gte=0), name="trip_hotel_child_no_bed_gte_0"),
            models.CheckConstraint(condition=Q(infant__gte=0), name="trip_hotel_infant_gte_0"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        trip = self.trip_hotel.stop.trip if self.trip_hotel_id else None
        if self.agency_id and trip and trip.agency_id != self.agency_id:
            errors["trip_hotel"] = "The trip hotel must belong to the same agency."
        if self.currency_id and not self.currency.is_active:
            errors["currency"] = "The currency must be active."
        if errors:
            raise ValidationError(errors)


class Promotion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="promotions"
    )
    trip = models.ForeignKey("trips.Trip", on_delete=models.CASCADE, related_name="promotions")
    code = models.SlugField(max_length=60)
    name = models.CharField(max_length=160)
    sales_start_date = models.DateField()
    sales_end_date = models.DateField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-sales_start_date", "name"]
        constraints = [
            models.UniqueConstraint(fields=["agency", "code"], name="uniq_promotion_code_agency"),
            models.CheckConstraint(
                condition=Q(sales_end_date__gte=F("sales_start_date")),
                name="promotion_sales_period_order",
            ),
        ]
        indexes = [models.Index(fields=["agency", "trip", "is_active"])]

    def __str__(self):
        return f"{self.code} - {self.name}"

    def clean(self):
        super().clean()
        if self.trip_id and self.trip.agency_id != self.agency_id:
            raise ValidationError({"trip": "The trip must belong to the same agency."})


class TripHotelPrice(models.Model):
    class BedBasis(models.TextChoices):
        STANDARD = "STANDARD", "Standard"
        WITH_BED = "WITH_BED", "With bed"
        WITHOUT_BED = "WITHOUT_BED", "Without bed"
        NOT_APPLICABLE = "N_A", "Not applicable"

    class PriceKind(models.TextChoices):
        STANDARD = "STANDARD", "Standard"
        PROMOTIONAL = "PROMOTIONAL", "Promotional"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="trip_hotel_prices"
    )
    trip_hotel = models.ForeignKey(
        "trips.TripHotel", on_delete=models.CASCADE, related_name="prices"
    )
    room_type = models.ForeignKey(
        "catalog.RoomType", on_delete=models.PROTECT, related_name="trip_prices"
    )
    passenger_category = models.ForeignKey(
        "reference.PassengerCategory", on_delete=models.PROTECT, related_name="hotel_prices"
    )
    bed_basis = models.CharField(max_length=12, choices=BedBasis.choices)
    price_kind = models.CharField(
        max_length=12, choices=PriceKind.choices, default=PriceKind.STANDARD
    )
    promotion = models.ForeignKey(
        Promotion, on_delete=models.PROTECT, related_name="hotel_prices", null=True, blank=True
    )
    scope = models.CharField(max_length=16, choices=[("HOTEL_STAY", "Hotel stay"), ("TRIP_PACKAGE", "Whole-trip package")], default="HOTEL_STAY")
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="hotel_prices"
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [
            "trip_hotel__stop__order",
            "room_type__sort_order",
            "passenger_category__sort_order",
            "bed_basis",
            "price_kind",
        ]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="hotel_price_amount_gte_0"),
            models.CheckConstraint(
                condition=Q(price_kind="STANDARD", promotion__isnull=True)
                | Q(price_kind="PROMOTIONAL", promotion__isnull=False),
                name="hotel_price_promotion_matches_kind",
            ),
            models.UniqueConstraint(
                fields=["trip_hotel", "room_type", "passenger_category", "bed_basis", "scope"],
                condition=Q(price_kind="STANDARD"),
                name="uniq_standard_trip_hotel_price",
            ),
            models.UniqueConstraint(
                fields=["trip_hotel", "room_type", "passenger_category", "bed_basis", "scope", "promotion"],
                condition=Q(price_kind="PROMOTIONAL"),
                name="uniq_promotional_trip_hotel_price",
            ),
        ]
        indexes = [models.Index(fields=["agency", "trip_hotel", "price_kind"])]

    def __str__(self):
        return f"{self.trip_hotel} {self.room_type} {self.passenger_category}: {self.amount}"

    def clean(self):
        super().clean()
        errors = {}
        trip = self.trip_hotel.stop.trip if self.trip_hotel_id else None
        if trip and trip.agency_id != self.agency_id:
            errors["trip_hotel"] = "The trip hotel must belong to the same agency."
        if self.room_type_id and self.room_type.agency_id != self.agency_id:
            errors["room_type"] = "The room type must belong to the same agency."
        if self.passenger_category_id:
            category_agency = self.passenger_category.agency_id
            if category_agency and category_agency != self.agency_id:
                errors["passenger_category"] = "The passenger category is unavailable."
        if self.promotion_id and (
            self.promotion.agency_id != self.agency_id
            or (trip and self.promotion.trip_id != trip.id)
        ):
            errors["promotion"] = "The promotion must belong to the same trip."
        if errors:
            raise ValidationError(errors)


class SeasonalFlightPrice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="seasonal_flight_prices"
    )
    trip = models.ForeignKey("trips.Trip", on_delete=models.CASCADE, related_name="flight_prices")
    fare_name = models.CharField(max_length=120)
    airline = models.ForeignKey(
        "catalog.Airline",
        on_delete=models.PROTECT,
        related_name="seasonal_prices",
        null=True,
        blank=True,
    )
    sales_start_date = models.DateField()
    sales_end_date = models.DateField()
    passenger_category = models.ForeignKey(
        "reference.PassengerCategory", on_delete=models.PROTECT, related_name="flight_prices"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="flight_prices"
    )
    source_reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sales_start_date", "fare_name", "passenger_category__sort_order"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="flight_price_amount_gte_0"),
            models.CheckConstraint(
                condition=Q(sales_end_date__gte=F("sales_start_date")),
                name="flight_price_sales_period_order",
            ),
            models.UniqueConstraint(
                fields=[
                    "trip",
                    "fare_name",
                    "sales_start_date",
                    "sales_end_date",
                    "passenger_category",
                ],
                name="uniq_seasonal_round_trip_fare",
            ),
        ]
        indexes = [models.Index(fields=["agency", "trip", "is_active"])]

    def __str__(self):
        return f"{self.trip.code} {self.fare_name}: {self.amount} {self.currency_id}"

    def clean(self):
        super().clean()
        if self.trip_id and self.trip.agency_id != self.agency_id:
            raise ValidationError({"trip": "The trip must belong to the same agency."})
        if self.passenger_category_id:
            category_agency = self.passenger_category.agency_id
            if category_agency and category_agency != self.agency_id:
                raise ValidationError({"passenger_category": "The category is unavailable."})


class Quote(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ISSUED = "ISSUED", "Issued"
        ACCEPTED = "ACCEPTED", "Accepted"
        EXPIRED = "EXPIRED", "Expired"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="quotes"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="quotes"
    )
    code = models.SlugField(max_length=60)
    customer = models.ForeignKey(
        "customers.Customer", on_delete=models.PROTECT, related_name="quotes"
    )
    trip = models.ForeignKey("trips.Trip", on_delete=models.PROTECT, related_name="quotes")
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="quotes"
    )
    accounting_currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="accounting_quotes"
    )
    accounting_exchange_rate = models.DecimalField(max_digits=18, decimal_places=8)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    valid_until = models.DateField()
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_quotes"
    )
    issued_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("view_all_quotes", "Can view all quotes in the agency")]
        constraints = [
            models.UniqueConstraint(fields=["agency", "code"], name="uniq_quote_code_agency"),
            models.CheckConstraint(
                condition=Q(accounting_exchange_rate__gt=0), name="quote_accounting_rate_gt_0"
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
            commercial_fields = [
                "agency_id",
                "branch_id",
                "code",
                "customer_id",
                "trip_id",
                "currency_id",
                "accounting_currency_id",
                "accounting_exchange_rate",
                "valid_until",
                "notes",
                "created_by_id",
            ]
            if (
                stored
                and stored.status != self.Status.DRAFT
                and any(
                    getattr(stored, field) != getattr(self, field) for field in commercial_fields
                )
            ):
                raise ValidationError("Issued quote commercial terms are immutable.")
        super().save(*args, **kwargs)

    @property
    def total(self):
        return sum((line.total_amount for line in self.lines.all()), Decimal("0"))

    def clean(self):
        super().clean()
        errors = {}
        for field_name in ["branch", "customer", "trip"]:
            value = getattr(self, field_name, None)
            if value and value.agency_id != self.agency_id:
                errors[field_name] = f"The {field_name} must belong to the same agency."
        if (
            self.currency_id == self.accounting_currency_id
            and self.accounting_exchange_rate != Decimal("1")
        ):
            errors["accounting_exchange_rate"] = "Same-currency exchange rate must equal 1."
        if errors:
            raise ValidationError(errors)


class QuoteLine(models.Model):
    class Kind(models.TextChoices):
        HOTEL = "HOTEL", "Hotel"
        FLIGHT = "FLIGHT", "Round-trip flight"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    hotel_price = models.ForeignKey(
        TripHotelPrice, on_delete=models.PROTECT, null=True, blank=True, related_name="quote_lines"
    )
    flight_price = models.ForeignKey(
        SeasonalFlightPrice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="quote_lines",
    )
    description = models.CharField(max_length=240)
    quantity = models.PositiveIntegerField(default=1)
    source_unit_amount = models.DecimalField(max_digits=18, decimal_places=4)
    source_currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="source_quote_lines"
    )
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8)
    unit_amount = models.DecimalField(max_digits=18, decimal_places=4)
    total_amount = models.DecimalField(max_digits=18, decimal_places=4)
    source_snapshot = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1), name="quote_line_quantity_gte_1"),
            models.CheckConstraint(condition=Q(exchange_rate__gt=0), name="quote_line_rate_gt_0"),
            models.CheckConstraint(
                condition=Q(kind="HOTEL", hotel_price__isnull=False, flight_price__isnull=True)
                | Q(kind="FLIGHT", hotel_price__isnull=True, flight_price__isnull=False),
                name="quote_line_source_matches_kind",
            ),
        ]

    def __str__(self):
        return self.description

    def save(self, *args, **kwargs):
        if (
            self.quote_id
            and not Quote.objects.filter(pk=self.quote_id, status=Quote.Status.DRAFT).exists()
        ):
            raise ValidationError("Issued quote lines are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if (
            self.quote_id
            and not Quote.objects.filter(pk=self.quote_id, status=Quote.Status.DRAFT).exists()
        ):
            raise ValidationError("Issued quote lines are immutable.")
        return super().delete(*args, **kwargs)


class QuoteSnapshot(models.Model):
    quote = models.OneToOneField(Quote, on_delete=models.PROTECT, related_name="snapshot")
    payload = models.JSONField()
    sha256 = models.CharField(max_length=64, unique=True)
    quote_total = models.DecimalField(max_digits=18, decimal_places=4)
    quote_currency = models.CharField(max_length=3)
    accounting_total = models.DecimalField(max_digits=18, decimal_places=4)
    accounting_currency = models.CharField(max_length=3)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Snapshot {self.quote.code}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Commercial snapshots are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Commercial snapshots cannot be deleted.")
