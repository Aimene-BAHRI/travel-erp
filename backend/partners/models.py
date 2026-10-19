import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Partner(models.Model):
    class Kind(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        COMPANY = "COMPANY", "Company"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="partners"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="partners"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.COMPANY)
    name = models.CharField(max_length=180)
    contact_name = models.CharField(max_length=160, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_partners"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        permissions = [("view_all_partners", "Can view all partners in the agency")]
        constraints = [
            models.UniqueConstraint(fields=["agency", "name"], name="uniq_partner_name_agency")
        ]
        indexes = [models.Index(fields=["agency", "branch", "is_active"])]

    def __str__(self):
        return self.name

    def clean(self):
        if self.branch_id and self.branch.agency_id != self.agency_id:
            raise ValidationError({"branch": "The branch must belong to the same agency."})


class PartnerAllocation(models.Model):
    class Kind(models.TextChoices):
        PACKAGE = "PACKAGE", "Package"
        TICKETS = "TICKETS", "Tickets"
        ROOMS = "ROOMS", "Rooms"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="partner_allocations"
    )
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="allocations")
    trip = models.ForeignKey(
        "trips.Trip", on_delete=models.PROTECT, related_name="partner_allocations"
    )
    kind = models.CharField(max_length=10, choices=Kind.choices)
    quantity = models.PositiveIntegerField()
    reserved_quantity = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_partner_allocations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["trip__departure_date", "partner__name", "kind"]
        constraints = [
            models.UniqueConstraint(
                fields=["partner", "trip", "kind"], name="uniq_partner_trip_allocation_kind"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1), name="partner_allocation_quantity_gte_1"
            ),
        ]
        indexes = [models.Index(fields=["agency", "trip", "kind"])]

    def __str__(self):
        return f"{self.partner.name} {self.trip.code} {self.kind}"

    @property
    def used_quantity(self):
        return sum(self.usages.values_list("quantity", flat=True))

    @property
    def remaining_quantity(self):
        return self.quantity - self.used_quantity - self.reserved_quantity

    def clean(self):
        if self.partner_id and self.partner.agency_id != self.agency_id:
            raise ValidationError({"partner": "The partner must belong to the same agency."})
        if self.trip_id and self.trip.agency_id != self.agency_id:
            raise ValidationError({"trip": "The trip must belong to the same agency."})
        if self.reserved_quantity and self.kind != self.Kind.TICKETS:
            raise ValidationError({"reserved_quantity": "Only ticket allocations can reserve ticket places."})
        if self.reserved_quantity > self.quantity - self.used_quantity:
            raise ValidationError({"reserved_quantity": "Reserved ticket places cannot exceed the allocation quantity."})


class PartnerAllocationUsage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    allocation = models.ForeignKey(
        PartnerAllocation, on_delete=models.PROTECT, related_name="usages"
    )
    booking = models.ForeignKey(
        "bookings.Booking", on_delete=models.PROTECT, related_name="partner_allocation_usages"
    )
    quantity = models.PositiveIntegerField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_allocation_usages"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["allocation", "booking"], name="uniq_allocation_booking_usage"
            ),
            models.CheckConstraint(
                condition=Q(quantity__gte=1), name="allocation_usage_quantity_gte_1"
            ),
        ]

    def __str__(self):
        return f"{self.allocation}: {self.booking.code} x {self.quantity}"


class PartnerCommission(models.Model):
    class Status(models.TextChoices):
        ACCRUED = "ACCRUED", "Accrued"
        APPROVED = "APPROVED", "Approved"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="partner_commissions"
    )
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name="commissions")
    booking = models.ForeignKey(
        "bookings.Booking", on_delete=models.PROTECT, related_name="partner_commissions"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="partner_commissions"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACCRUED)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_partner_commissions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["partner", "booking"], name="uniq_partner_booking_commission"
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=0), name="partner_commission_amount_gte_0"
            ),
        ]
        indexes = [models.Index(fields=["agency", "partner", "status"])]

    def __str__(self):
        return f"{self.partner.name}: {self.booking.code}"

    @property
    def paid_amount(self):
        return sum(
            (item.signed_commission_amount for item in self.payments.select_related("reverses")),
            Decimal("0"),
        )

    @property
    def remaining_amount(self):
        return self.amount - self.paid_amount


class CommissionPayment(models.Model):
    class Kind(models.TextChoices):
        PAYMENT = "PAYMENT", "Payment"
        REVERSAL = "REVERSAL", "Reversal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="commission_payments"
    )
    commission = models.ForeignKey(
        PartnerCommission, on_delete=models.PROTECT, related_name="payments"
    )
    number = models.CharField(max_length=40)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="commission_payments"
    )
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8)
    commission_amount = models.DecimalField(max_digits=18, decimal_places=4)
    payment_method = models.ForeignKey(
        "reference.PaymentMethod", on_delete=models.PROTECT, related_name="commission_payments"
    )
    payment_date = models.DateField()
    reference = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    reverses = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversal"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_commission_payments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["agency", "number"], name="uniq_commission_payment_number"
            ),
            models.CheckConstraint(
                condition=Q(amount__gt=0), name="commission_payment_amount_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(exchange_rate__gt=0), name="commission_payment_rate_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(commission_amount__gt=0), name="commission_payment_converted_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(kind="REVERSAL", reverses__isnull=False)
                | Q(kind="PAYMENT", reverses__isnull=True),
                name="commission_reversal_source_matches_kind",
            ),
        ]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Commission payments are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Commission payments cannot be deleted; reverse them.")

    @property
    def signed_commission_amount(self):
        return self.commission_amount if self.kind == self.Kind.PAYMENT else -self.commission_amount
