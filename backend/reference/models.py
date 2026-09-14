import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Country(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120, unique=True)
    code = models.CharField(max_length=2, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)


class City(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="cities")
    name = models.CharField(max_length=120)

    class Meta:
        ordering = ["country__name", "name"]
        verbose_name_plural = "cities"
        constraints = [
            models.UniqueConstraint(fields=["country", "name"], name="uniq_city_name_country")
        ]
        indexes = [models.Index(fields=["country", "name"])]

    def __str__(self):
        return f"{self.name}, {self.country.code}"


class Currency(models.Model):
    code = models.CharField(primary_key=True, max_length=3)
    name = models.CharField(max_length=80)
    symbol = models.CharField(max_length=8, blank=True)
    decimal_places = models.PositiveSmallIntegerField(default=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name_plural = "currencies"
        constraints = [
            models.CheckConstraint(
                condition=Q(decimal_places__lte=4), name="currency_decimal_places_lte_4"
            )
        ]

    def __str__(self):
        return self.code

    def save(self, *args, **kwargs):
        self.code = self.code.upper()
        super().save(*args, **kwargs)


class AgencyCurrency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.CASCADE, related_name="currency_settings"
    )
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="agency_settings")
    is_enabled = models.BooleanField(default=True)
    is_accounting = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["currency_id"]
        constraints = [
            models.UniqueConstraint(fields=["agency", "currency"], name="uniq_agency_currency"),
            models.UniqueConstraint(
                fields=["agency"],
                condition=Q(is_accounting=True),
                name="uniq_accounting_currency_agency",
            ),
            models.CheckConstraint(
                condition=Q(is_accounting=False) | Q(is_enabled=True),
                name="accounting_currency_must_be_enabled",
            ),
        ]

    def __str__(self):
        return f"{self.agency}: {self.currency_id}"


class AgencyOwnedReference(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.CASCADE, null=True, blank=True
    )
    code = models.SlugField(max_length=30)
    name = models.CharField(max_length=80)
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.is_system != (self.agency_id is None):
            raise ValidationError(
                "System records must be global and custom records must have an agency."
            )


class PassengerCategory(AgencyOwnedReference):
    requires_bed_by_default = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "passenger categories"
        constraints = [
            models.CheckConstraint(
                condition=Q(is_system=True, agency__isnull=True)
                | Q(is_system=False, agency__isnull=False),
                name="passenger_category_system_ownership",
            ),
            models.UniqueConstraint(
                fields=["agency", "code"], name="uniq_passenger_category_code_agency"
            ),
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(is_system=True),
                name="uniq_system_passenger_category_code",
            ),
        ]


class PaymentMethod(AgencyOwnedReference):
    class Meta:
        ordering = ["sort_order", "name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(is_system=True, agency__isnull=True)
                | Q(is_system=False, agency__isnull=False),
                name="payment_method_system_ownership",
            ),
            models.UniqueConstraint(
                fields=["agency", "code"], name="uniq_payment_method_code_agency"
            ),
            models.UniqueConstraint(
                fields=["code"], condition=Q(is_system=True), name="uniq_system_payment_method_code"
            ),
        ]
