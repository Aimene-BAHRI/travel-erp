import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="suppliers"
    )
    name = models.CharField(max_length=180)
    legal_name = models.CharField(max_length=220, blank=True)
    registration_number = models.CharField(max_length=100, blank=True)
    tax_number = models.CharField(max_length=100, blank=True)
    contact_name = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["agency", "name"], name="uniq_supplier_name_agency")
        ]
        indexes = [models.Index(fields=["agency", "is_active", "name"])]

    def __str__(self):
        return self.name


class Airline(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160, unique=True)
    iata_code = models.CharField(max_length=2, unique=True, null=True, blank=True)
    icao_code = models.CharField(max_length=3, unique=True, null=True, blank=True)
    country = models.ForeignKey(
        "reference.Country",
        on_delete=models.PROTECT,
        related_name="airlines",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.iata_code = self.iata_code.upper() if self.iata_code else None
        self.icao_code = self.icao_code.upper() if self.icao_code else None
        super().save(*args, **kwargs)


class Hotel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="hotels"
    )
    city = models.ForeignKey("reference.City", on_delete=models.PROTECT, related_name="hotels")
    name = models.CharField(max_length=180)
    star_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    check_in_time = models.TimeField(null=True, blank=True)
    check_out_time = models.TimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["agency", "city", "name"], name="uniq_hotel_name_city_agency"
            ),
            models.CheckConstraint(
                condition=Q(star_rating__isnull=True) | Q(star_rating__gte=1, star_rating__lte=5),
                name="hotel_star_rating_1_to_5",
            ),
        ]
        indexes = [
            models.Index(fields=["agency", "city", "is_active"]),
            models.Index(fields=["agency", "name"]),
        ]

    def __str__(self):
        return self.name


class RoomType(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="room_types"
    )
    code = models.SlugField(max_length=40)
    name = models.CharField(max_length=100)
    default_standard_beds = models.PositiveSmallIntegerField(default=1)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["agency", "code"], name="uniq_room_type_code_agency"),
            models.UniqueConstraint(fields=["agency", "name"], name="uniq_room_type_name_agency"),
            models.CheckConstraint(
                condition=Q(default_standard_beds__gte=1),
                name="room_type_default_beds_gte_1",
            ),
        ]

    def __str__(self):
        return self.name


class Room(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="hotel_rooms"
    )
    hotel = models.ForeignKey(Hotel, on_delete=models.PROTECT, related_name="rooms")
    room_type = models.ForeignKey(RoomType, on_delete=models.PROTECT, related_name="rooms")
    number = models.CharField(max_length=30)
    floor = models.CharField(max_length=30, blank=True)
    standard_beds = models.PositiveSmallIntegerField()
    max_extra_beds = models.PositiveSmallIntegerField(default=0)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["hotel__name", "number"]
        constraints = [
            models.UniqueConstraint(fields=["hotel", "number"], name="uniq_room_number_hotel"),
            models.CheckConstraint(
                condition=Q(standard_beds__gte=1), name="room_standard_beds_gte_1"
            ),
        ]
        indexes = [
            models.Index(fields=["agency", "hotel", "is_active"]),
            models.Index(fields=["hotel", "room_type"]),
        ]

    def __str__(self):
        return f"{self.hotel.name} - {self.number}"

    @property
    def maximum_beds(self):
        return self.standard_beds + self.max_extra_beds

    def clean(self):
        super().clean()
        errors = {}
        if self.hotel_id and self.hotel.agency_id != self.agency_id:
            errors["hotel"] = "The hotel must belong to the same agency."
        if self.room_type_id and self.room_type.agency_id != self.agency_id:
            errors["room_type"] = "The room type must belong to the same agency."
        if errors:
            raise ValidationError(errors)
