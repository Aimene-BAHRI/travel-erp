from decimal import Decimal

from django.db.models import Q
from rest_framework import serializers

from bookings.models import Booking
from catalog.models import Supplier
from finance.models import (
    AgencyCashEntry,
    ExchangeRate,
    ExpensePayment,
    FinancialTransaction,
    PaymentAllocation,
    TripExpense,
)
from organizations.models import Branch
from reference.models import Currency, PaymentMethod
from trips.models import Trip


class ExchangeRateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExchangeRate
        fields = [
            "id",
            "source_currency",
            "target_currency",
            "rate",
            "effective_date",
            "source_reference",
            "notes",
            "created_by",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            currencies = Currency.objects.filter(
                agency_settings__agency=request.user.agency,
                agency_settings__is_enabled=True,
            )
            self.fields["source_currency"].queryset = currencies
            self.fields["target_currency"].queryset = currencies

    def validate(self, attrs):
        if attrs.get("source_currency") == attrs.get("target_currency"):
            raise serializers.ValidationError("Source and target currencies must differ.")
        return attrs


class PaymentAllocationSerializer(serializers.ModelSerializer):
    traveler_name = serializers.CharField(
        source="booking_traveler.traveler.display_name", read_only=True
    )

    class Meta:
        model = PaymentAllocation
        fields = ["id", "booking_traveler", "traveler_name", "amount"]
        read_only_fields = fields


class FinancialTransactionSerializer(serializers.ModelSerializer):
    booking_code = serializers.CharField(source="booking.code", read_only=True)
    currency_code = serializers.CharField(source="currency_id", read_only=True)
    booking_currency_code = serializers.CharField(source="booking_currency_id", read_only=True)
    accounting_currency_code = serializers.CharField(
        source="accounting_currency_id", read_only=True
    )
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    signed_booking_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True
    )
    allocations = PaymentAllocationSerializer(
        source="traveler_allocations", many=True, read_only=True
    )

    class Meta:
        model = FinancialTransaction
        fields = [
            "id",
            "booking",
            "booking_code",
            "number",
            "kind",
            "amount",
            "currency",
            "currency_code",
            "booking_exchange_rate",
            "booking_amount",
            "booking_currency",
            "booking_currency_code",
            "signed_booking_amount",
            "allocations",
            "accounting_amount",
            "accounting_currency",
            "accounting_currency_code",
            "payment_method",
            "payment_method_name",
            "transaction_date",
            "reference",
            "notes",
            "reverses",
            "created_by",
            "created_at",
        ]
        read_only_fields = fields


class AllocationInputSerializer(serializers.Serializer):
    booking_traveler = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))


class PostTransactionSerializer(serializers.Serializer):
    booking = serializers.PrimaryKeyRelatedField(queryset=Booking.objects.none())
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    currency = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.none())
    booking_exchange_rate = serializers.DecimalField(
        max_digits=18, decimal_places=8, min_value=Decimal("0.00000001")
    )
    payment_method = serializers.PrimaryKeyRelatedField(queryset=PaymentMethod.objects.none())
    transaction_date = serializers.DateField()
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    allocations = AllocationInputSerializer(many=True, required=False, default=list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            bookings = Booking.objects.filter(agency=agency)
            if request.user.branch_id and not request.user.has_perm("bookings.view_all_bookings"):
                bookings = bookings.filter(branch=request.user.branch)
            self.fields["booking"].queryset = bookings
            self.fields["currency"].queryset = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )
            self.fields["payment_method"].queryset = PaymentMethod.objects.filter(
                Q(is_system=True) | Q(agency=agency), is_active=True
            )


class ReversalSerializer(serializers.Serializer):
    transaction_date = serializers.DateField()
    reason = serializers.CharField(allow_blank=False)


class FinancialSummarySerializer(serializers.Serializer):
    booking_total = serializers.DecimalField(max_digits=18, decimal_places=4)
    paid_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    remaining_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    currency = serializers.CharField()
    accounting_total = serializers.DecimalField(max_digits=18, decimal_places=4)
    accounting_paid_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    accounting_remaining_amount = serializers.DecimalField(max_digits=18, decimal_places=4)
    accounting_currency = serializers.CharField()
    traveler_balances = serializers.ListField(child=serializers.DictField())


class ExpensePaymentSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency_id", read_only=True)
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    signed_expense_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True
    )

    class Meta:
        model = ExpensePayment
        fields = [
            "id",
            "expense",
            "number",
            "kind",
            "amount",
            "currency",
            "currency_code",
            "exchange_rate",
            "expense_amount",
            "signed_expense_amount",
            "payment_method",
            "payment_method_name",
            "payment_date",
            "reference",
            "notes",
            "reverses",
            "created_at",
        ]
        read_only_fields = fields


class TripExpenseSerializer(serializers.ModelSerializer):
    trip_name = serializers.CharField(source="trip.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    currency_code = serializers.CharField(source="currency_id", read_only=True)
    paid_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    payments = ExpensePaymentSerializer(many=True, read_only=True)

    class Meta:
        model = TripExpense
        fields = [
            "id",
            "trip",
            "trip_name",
            "supplier",
            "supplier_name",
            "category",
            "description",
            "amount",
            "currency",
            "currency_code",
            "paid_amount",
            "remaining_amount",
            "due_date",
            "status",
            "notes",
            "payments",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "paid_amount",
            "remaining_amount",
            "payments",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["trip"].queryset = Trip.objects.filter(agency=agency)
            self.fields["supplier"].queryset = Supplier.objects.filter(
                agency=agency, is_active=True
            )
            self.fields["currency"].queryset = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )

    def validate(self, attrs):
        trip = attrs.get("trip", self.instance.trip if self.instance else None)
        supplier = attrs.get("supplier", self.instance.supplier if self.instance else None)
        if supplier and trip and supplier.agency_id != trip.agency_id:
            raise serializers.ValidationError(
                {"supplier": "Supplier must belong to the trip agency."}
            )
        return attrs


class ExpensePaymentInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    currency = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.none())
    exchange_rate = serializers.DecimalField(
        max_digits=18, decimal_places=8, min_value=Decimal("0.00000001")
    )
    payment_method = serializers.PrimaryKeyRelatedField(queryset=PaymentMethod.objects.none())
    payment_date = serializers.DateField()
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["currency"].queryset = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )
            self.fields["payment_method"].queryset = PaymentMethod.objects.filter(
                Q(is_system=True) | Q(agency=agency), is_active=True
            )


class AgencyCashEntrySerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency_id", read_only=True)
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    trip_name = serializers.CharField(source="trip.name", read_only=True)
    signed_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = AgencyCashEntry
        fields = ["id", "branch", "trip", "trip_name", "number", "direction", "category",
              "description", "recipient_name", "amount", "signed_amount", "currency", "currency_code",
              "source_amount", "source_currency", "exchange_rate", "payment_method", "payment_method_name",
              "entry_date", "reference", "notes", "created_by", "created_at"]
        read_only_fields = fields


class AgencyCashEntryInputSerializer(serializers.Serializer):
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none())
    trip = serializers.PrimaryKeyRelatedField(queryset=Trip.objects.none(), required=False, allow_null=True)
    direction = serializers.ChoiceField(choices=AgencyCashEntry.Direction.choices)
    category = serializers.ChoiceField(choices=AgencyCashEntry.Category.choices)
    description = serializers.CharField(max_length=180)
    recipient_name = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    currency = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.none())
    source_amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"), required=False, allow_null=True)
    source_currency = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.none(), required=False, allow_null=True)
    exchange_rate = serializers.DecimalField(max_digits=18, decimal_places=8, min_value=Decimal("0.00000001"), required=False, allow_null=True)
    payment_method = serializers.PrimaryKeyRelatedField(queryset=PaymentMethod.objects.none())
    entry_date = serializers.DateField()
    reference = serializers.CharField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["branch"].queryset = Branch.objects.filter(agency=agency)
            self.fields["trip"].queryset = Trip.objects.filter(agency=agency)
            self.fields["currency"].queryset = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )
            self.fields["source_currency"].queryset = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )
            self.fields["payment_method"].queryset = PaymentMethod.objects.filter(
                Q(is_system=True) | Q(agency=agency), is_active=True
            )
