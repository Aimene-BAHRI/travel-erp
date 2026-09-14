from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import serializers

from bookings.models import Booking
from organizations.models import Branch
from partners.models import CommissionPayment, Partner, PartnerAllocation, PartnerCommission
from reference.models import Currency, PaymentMethod
from trips.models import Trip


class CleanSerializer(serializers.ModelSerializer):
    def create(self, data):
        instance = self.Meta.model(**data)
        try:
            instance.full_clean()
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict or exc.messages) from exc
        return instance

    def update(self, instance, data):
        for key, value in data.items():
            setattr(instance, key, value)
        try:
            instance.full_clean()
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict or exc.messages) from exc
        return instance


class PartnerSerializer(CleanSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Partner
        fields = [
            "id",
            "branch",
            "branch_name",
            "kind",
            "name",
            "contact_name",
            "phone",
            "email",
            "address",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["branch"].queryset = Branch.objects.filter(agency=request.user.agency)


class AllocationSerializer(CleanSerializer):
    partner_name = serializers.CharField(source="partner.name", read_only=True)
    trip_name = serializers.CharField(source="trip.name", read_only=True)
    used_quantity = serializers.IntegerField(read_only=True)
    remaining_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = PartnerAllocation
        fields = [
            "id",
            "partner",
            "partner_name",
            "trip",
            "trip_name",
            "kind",
            "quantity",
            "used_quantity",
            "remaining_quantity",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "used_quantity", "remaining_quantity", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["partner"].queryset = Partner.objects.filter(
                agency=request.user.agency, is_active=True
            )
            self.fields["trip"].queryset = Trip.objects.filter(agency=request.user.agency)

    def validate_quantity(self, value):
        if self.instance and value < self.instance.used_quantity:
            raise serializers.ValidationError("Quantity cannot be below existing usage.")
        return value


class CommissionSerializer(CleanSerializer):
    partner_name = serializers.CharField(source="partner.name", read_only=True)
    booking_code = serializers.CharField(source="booking.code", read_only=True)
    paid_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    remaining_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = PartnerCommission
        fields = [
            "id",
            "partner",
            "partner_name",
            "booking",
            "booking_code",
            "amount",
            "currency",
            "status",
            "paid_amount",
            "remaining_amount",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "paid_amount",
            "remaining_amount",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["partner"].queryset = Partner.objects.filter(agency=agency, is_active=True)
            self.fields["booking"].queryset = Booking.objects.filter(agency=agency)
            self.fields["currency"].queryset = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )


class CommissionPaymentSerializer(serializers.ModelSerializer):
    payment_method_name = serializers.CharField(source="payment_method.name", read_only=True)
    signed_commission_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, read_only=True
    )

    class Meta:
        model = CommissionPayment
        fields = [
            "id",
            "commission",
            "number",
            "kind",
            "amount",
            "currency",
            "exchange_rate",
            "commission_amount",
            "signed_commission_amount",
            "payment_method",
            "payment_method_name",
            "payment_date",
            "reference",
            "notes",
            "reverses",
            "created_at",
        ]
        read_only_fields = fields


class UsageInputSerializer(serializers.Serializer):
    booking = serializers.PrimaryKeyRelatedField(queryset=Booking.objects.none())
    quantity = serializers.IntegerField(min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["booking"].queryset = Booking.objects.filter(agency=request.user.agency)


class CommissionTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[PartnerCommission.Status.APPROVED, PartnerCommission.Status.CANCELLED]
    )


class PaymentInputSerializer(serializers.Serializer):
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


class ReversalInputSerializer(serializers.Serializer):
    payment_date = serializers.DateField()
    reason = serializers.CharField(allow_blank=False)
