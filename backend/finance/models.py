import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class AirlinePricing(models.Model):
    trip = models.OneToOneField(
        "trips.Trip", primary_key=True, on_delete=models.CASCADE, related_name="airline_pricing"
    )
    rows = models.JSONField(default=list)
    visa_price = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def quantities_from_bookings(self):
        return self.trip.max_travelers is not None or self.trip.bookings.exists()

    @property
    def passenger_counts(self):
        from collections import Counter
        from bookings.models import BookingTraveler

        counts = Counter()
        for link in BookingTraveler.objects.filter(
            booking__trip_id=self.trip_id, booking__status__in=["CONFIRMED", "COMPLETED"]
        ).exclude(service_type="VISA_ONLY").select_related("passenger_category"):
            code = link.passenger_category.code.upper()
            if code != "INF" and link.seat_required is False:
                continue
            category = "ADULT" if code == "ADT" else code
            if code == "INF" and link.seat_required:
                category = "INF_SEAT"
            counts[category] += 1
        return counts

    @property
    def unbooked_seats(self):
        if self.trip.max_travelers is None:
            return 0
        counts = self.passenger_counts
        adjustments = sum(row["seats"] for row in self.rows if row["category"] in {
            "FREE", "DISCOUNT_50", "DISCOUNT_60", "DISCOUNT_100"
        })
        return max(0, self.trip.max_travelers - counts["ADULT"] - counts["CHD"]
                   - counts["INF_SEAT"] - adjustments)

    @property
    def effective_rows(self):
        rows = [dict(row) for row in self.rows]
        if not any(row["category"] == "INF_SEAT" for row in rows):
            rows.append({"category": "INF_SEAT", "seats": 0, "price": None})
        if self.quantities_from_bookings:
            counts = self.passenger_counts
            for row in rows:
                if row["category"] in {"ADULT", "CHD", "INF", "INF_SEAT"}:
                    row["seats"] = counts[row["category"]]
                    if row["category"] == "ADULT":
                        row["seats"] += self.unbooked_seats
        return rows

    @property
    def total(self):
        rows = self.effective_rows
        missing = [row["category"] for row in rows if row["seats"] and row["price"] is None]
        if missing:
            raise ValidationError(f"Enter missing airline fares before continuing: {', '.join(missing)}.")
        return sum((Decimal(row["price"]) * row["seats"] for row in rows
                    if row["price"] is not None), Decimal("0"))


class AirlineInstallment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pricing = models.ForeignKey(
        AirlinePricing, on_delete=models.PROTECT, related_name="installments"
    )
    cash_entry = models.OneToOneField("finance.AgencyCashEntry", on_delete=models.PROTECT, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True, db_index=True)
    scheduled_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True, blank=True)
    scheduled_reference = models.CharField(max_length=160, blank=True)
    scheduled_notes = models.TextField(blank=True)
    attachment = models.FileField(upload_to="airline-installments/%Y/%m/", blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="voided_airline_installments",
    )
    reversal_cash_entry = models.OneToOneField(
        "finance.AgencyCashEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reversed_airline_installment",
    )

    class Meta:
        ordering = ["cash_entry__entry_date", "cash_entry__created_at"]


class ExchangeRate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="exchange_rates"
    )
    source_currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="source_exchange_rates"
    )
    target_currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="target_exchange_rates"
    )
    rate = models.DecimalField(max_digits=18, decimal_places=8)
    effective_date = models.DateField()
    source_reference = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_exchange_rates"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-effective_date", "source_currency_id", "target_currency_id"]
        constraints = [
            models.CheckConstraint(condition=Q(rate__gt=0), name="exchange_rate_gt_0"),
            models.CheckConstraint(
                condition=~Q(source_currency=F("target_currency")),
                name="exchange_rate_currencies_differ",
            ),
            models.UniqueConstraint(
                fields=["agency", "source_currency", "target_currency", "effective_date"],
                name="uniq_exchange_rate_agency_pair_date",
            ),
        ]
        indexes = [
            models.Index(fields=["agency", "source_currency", "target_currency", "effective_date"])
        ]

    def __str__(self):
        return f"{self.source_currency_id}/{self.target_currency_id} {self.rate}"

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Historical exchange rates are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Historical exchange rates cannot be deleted.")


class FinancialTransaction(models.Model):
    class Kind(models.TextChoices):
        PAYMENT = "PAYMENT", "Payment"
        REFUND = "REFUND", "Refund"
        REVERSAL = "REVERSAL", "Reversal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="financial_transactions"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="financial_transactions"
    )
    booking = models.ForeignKey(
        "bookings.Booking", on_delete=models.PROTECT, related_name="financial_transactions"
    )
    number = models.CharField(max_length=40)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="financial_transactions"
    )
    booking_exchange_rate = models.DecimalField(max_digits=18, decimal_places=8)
    booking_amount = models.DecimalField(max_digits=18, decimal_places=4)
    booking_currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="booking_value_transactions"
    )
    accounting_amount = models.DecimalField(max_digits=18, decimal_places=4)
    accounting_currency = models.ForeignKey(
        "reference.Currency",
        on_delete=models.PROTECT,
        related_name="accounting_value_transactions",
    )
    payment_method = models.ForeignKey(
        "reference.PaymentMethod", on_delete=models.PROTECT, related_name="transactions"
    )
    transaction_date = models.DateField()
    reference = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    reverses = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reversal",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_financial_transactions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        permissions = [
            ("view_all_financial_transactions", "Can view all agency financial transactions")
        ]
        constraints = [
            models.UniqueConstraint(fields=["agency", "number"], name="uniq_financial_number"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="financial_amount_gt_0"),
            models.CheckConstraint(
                condition=Q(booking_exchange_rate__gt=0), name="financial_booking_rate_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(booking_amount__gt=0), name="financial_booking_amount_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(accounting_amount__gt=0), name="financial_accounting_amount_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(kind="REVERSAL", reverses__isnull=False)
                | Q(kind__in=["PAYMENT", "REFUND"], reverses__isnull=True),
                name="financial_reversal_source_matches_kind",
            ),
        ]
        indexes = [
            models.Index(fields=["agency", "branch", "transaction_date"]),
            models.Index(fields=["booking", "transaction_date"]),
        ]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Posted financial transactions are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Posted financial transactions cannot be deleted; reverse them.")

    @property
    def direction(self):
        if self.kind == self.Kind.PAYMENT:
            return Decimal("1")
        if self.kind == self.Kind.REFUND:
            return Decimal("-1")
        return -self.reverses.direction

    @property
    def signed_booking_amount(self):
        return self.booking_amount * self.direction

    @property
    def signed_accounting_amount(self):
        return self.accounting_amount * self.direction


class PaymentAllocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        FinancialTransaction, on_delete=models.PROTECT, related_name="traveler_allocations"
    )
    booking_traveler = models.ForeignKey(
        "bookings.BookingTraveler", on_delete=models.PROTECT, related_name="payment_allocations"
    )
    amount = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["transaction", "booking_traveler"],
                name="uniq_payment_allocation_traveler",
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_allocation_gt_0"),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Payment allocations are immutable.")
        if self.transaction.booking_id != self.booking_traveler.booking_id:
            raise ValidationError(
                "Payment allocation traveler must belong to the transaction booking."
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.transaction.number} - {self.booking_traveler_id}: {self.amount}"

    def delete(self, *args, **kwargs):
        raise ValidationError("Payment allocations cannot be deleted; reverse the payment.")


class TripExpense(models.Model):
    class Category(models.TextChoices):
        HOTEL = "HOTEL", "Hotel"
        FLIGHT = "FLIGHT", "Flight"
        TRANSPORT = "TRANSPORT", "Transport"
        VISA = "VISA", "Visa"
        GUIDE = "GUIDE", "Guide"
        OTHER = "OTHER", "Other"

    class Status(models.TextChoices):
        PLANNED = "PLANNED", "Planned"
        APPROVED = "APPROVED", "Approved"
        CANCELLED = "CANCELLED", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="trip_expenses"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="trip_expenses"
    )
    trip = models.ForeignKey("trips.Trip", on_delete=models.PROTECT, related_name="expenses")
    supplier = models.ForeignKey(
        "catalog.Supplier",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="trip_expenses",
    )
    category = models.CharField(max_length=12, choices=Category.choices)
    description = models.CharField(max_length=180)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="trip_expenses"
    )
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PLANNED)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_trip_expenses"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="trip_expense_amount_gte_0")
        ]
        indexes = [models.Index(fields=["agency", "trip", "status"])]

    @property
    def paid_amount(self):
        return sum(
            (entry.signed_expense_amount for entry in self.payments.select_related("reverses")),
            Decimal("0"),
        )

    @property
    def remaining_amount(self):
        return self.amount - self.paid_amount

    def clean(self):
        super().clean()
        errors = {}
        if self.trip_id and self.trip.agency_id != self.agency_id:
            errors["trip"] = "Trip must belong to the same agency."
        if self.branch_id and self.branch.agency_id != self.agency_id:
            errors["branch"] = "Branch must belong to the same agency."
        if self.trip_id and self.branch_id and self.trip.branch_id != self.branch_id:
            errors["branch"] = "Expense branch must match the trip branch."
        if self.supplier_id and self.supplier.agency_id != self.agency_id:
            errors["supplier"] = "Supplier must belong to the same agency."
        if errors:
            raise ValidationError(errors)


class ExpensePayment(models.Model):
    class Kind(models.TextChoices):
        PAYMENT = "PAYMENT", "Payment"
        REVERSAL = "REVERSAL", "Reversal"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="expense_payments"
    )
    expense = models.ForeignKey(TripExpense, on_delete=models.PROTECT, related_name="payments")
    number = models.CharField(max_length=40)
    kind = models.CharField(max_length=10, choices=Kind.choices)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="expense_payments"
    )
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8)
    expense_amount = models.DecimalField(max_digits=18, decimal_places=4)
    payment_method = models.ForeignKey(
        "reference.PaymentMethod", on_delete=models.PROTECT, related_name="expense_payments"
    )
    payment_date = models.DateField()
    reference = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    reverses = models.OneToOneField(
        "self", on_delete=models.PROTECT, null=True, blank=True, related_name="reversal"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_expense_payments"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["agency", "number"], name="uniq_expense_payment_number"
            ),
            models.CheckConstraint(condition=Q(amount__gt=0), name="expense_payment_amount_gt_0"),
            models.CheckConstraint(
                condition=Q(exchange_rate__gt=0), name="expense_payment_rate_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(expense_amount__gt=0), name="expense_payment_converted_gt_0"
            ),
            models.CheckConstraint(
                condition=Q(kind="REVERSAL", reverses__isnull=False)
                | Q(kind="PAYMENT", reverses__isnull=True),
                name="expense_reversal_source_matches_kind",
            ),
        ]

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Expense payments are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Expense payments cannot be deleted; reverse them.")

    @property
    def signed_expense_amount(self):
        return self.expense_amount if self.kind == self.Kind.PAYMENT else -self.expense_amount


class AgencyCashEntry(models.Model):
    reverses = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal")

    class Direction(models.TextChoices):
        IN = "IN", "Money in"
        OUT = "OUT", "Money out"

    class Category(models.TextChoices):
        OTHER_INCOME = "OTHER_INCOME", "Other income"
        OWNER_FUNDS = "OWNER_FUNDS", "Owner funds"
        OPERATING_COST = "OPERATING_COST", "Operating cost"
        TAX = "TAX", "Tax"
        SALARY = "SALARY", "Salary"
        TRANSFER = "TRANSFER", "Transfer"
        TRIP_ADVANCE = "TRIP_ADVANCE", "Trip advance"
        OTHER_EXPENSE = "OTHER_EXPENSE", "Other expense"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="cash_entries"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="cash_entries"
    )
    trip = models.ForeignKey(
        "trips.Trip", on_delete=models.PROTECT, null=True, blank=True, related_name="cash_entries"
    )
    number = models.CharField(max_length=40)
    direction = models.CharField(max_length=3, choices=Direction.choices)
    category = models.CharField(max_length=20, choices=Category.choices)
    description = models.CharField(max_length=180)
    recipient_name = models.CharField(max_length=160, blank=True)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    currency = models.ForeignKey(
        "reference.Currency", on_delete=models.PROTECT, related_name="agency_cash_entries"
    )
    source_amount = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    source_currency = models.ForeignKey(
        "reference.Currency",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="source_agency_cash_entries",
    )
    exchange_rate = models.DecimalField(max_digits=18, decimal_places=8, null=True, blank=True)
    payment_method = models.ForeignKey(
        "reference.PaymentMethod", on_delete=models.PROTECT, related_name="agency_cash_entries"
    )
    entry_date = models.DateField()
    reference = models.CharField(max_length=160, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_cash_entries"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-entry_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["agency", "number"], name="uniq_agency_cash_number"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="agency_cash_amount_gt_0"),
            models.CheckConstraint(
                condition=Q(source_amount__isnull=True) | Q(source_amount__gt=0),
                name="agency_cash_source_amount_gt_0",
            ),
            models.CheckConstraint(
                condition=Q(exchange_rate__isnull=True) | Q(exchange_rate__gt=0),
                name="agency_cash_exchange_rate_gt_0",
            ),
        ]
        indexes = [
            models.Index(fields=["agency", "entry_date"]),
            models.Index(fields=["agency", "trip", "entry_date"]),
        ]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Cash entries are immutable.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Cash entries cannot be deleted; post an opposite entry.")

    @property
    def signed_amount(self):
        return self.amount if self.direction == self.Direction.IN else -self.amount

    def clean(self):
        super().clean()
        errors = {}
        if self.branch_id and self.branch.agency_id != self.agency_id:
            errors["branch"] = "Branch must belong to the same agency."
        if self.trip_id:
            if self.trip.agency_id != self.agency_id:
                errors["trip"] = "Trip must belong to the same agency."
            elif self.branch_id and self.trip.branch_id != self.branch_id:
                errors["branch"] = "Entry branch must match the trip branch."
        if errors:
            raise ValidationError(errors)
