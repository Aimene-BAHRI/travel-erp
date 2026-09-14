from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import serializers

from catalog.models import Airline, RoomType
from customers.models import Customer
from organizations.models import Branch
from pricing.models import (
    Promotion,
    Quote,
    QuoteLine,
    QuoteSnapshot,
    SeasonalFlightPrice,
    TripCostComponent,
    TripHotelPrice,
    TripOccupancyPackage,
)
from reference.models import Currency, PassengerCategory
from trips.models import Trip, TripHotel


class CleanModelSerializer(serializers.ModelSerializer):
    def _save_clean(self, instance):
        try:
            instance.full_clean()
            instance.save()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(getattr(exc, "message_dict", exc.messages)) from exc
        return instance

    def create(self, validated_data):
        return self._save_clean(self.Meta.model(**validated_data))

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        return self._save_clean(instance)


class TripCostComponentSerializer(CleanModelSerializer):
    currency_code = serializers.CharField(source="source_currency_id", read_only=True)
    converted_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = TripCostComponent
        fields = [
            "id",
            "trip",
            "code",
            "label",
            "basis",
            "applies_to",
            "source_amount",
            "source_currency",
            "currency_code",
            "exchange_rate",
            "quantity",
            "converted_amount",
            "is_active",
        ]
        read_only_fields = ["id", "converted_amount"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["trip"].queryset = Trip.objects.filter(agency=agency)
            self.fields["source_currency"].queryset = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )


class TripOccupancyPackageSerializer(CleanModelSerializer):
    calculated = serializers.SerializerMethodField()

    def validate(self, attrs):
        if self.instance is None and not attrs.get("adult_price"):
            raise serializers.ValidationError({"adult_price": "Select a hotel-specific adult package price."})
        return super().validate(attrs)

    class Meta:
        model = TripOccupancyPackage
        fields = [
            "id",
            "trip",
            "adult_price",
            "code",
            "name",
            "makkah_occupancy",
            "madinah_occupancy",
            "margin_adult",
            "margin_child_bed",
            "margin_child_no_bed",
            "margin_infant",
            "override_adult",
            "override_child_bed",
            "override_child_no_bed",
            "override_infant",
            "rounding_increment",
            "is_published",
            "calculated",
        ]
        read_only_fields = ["id", "calculated"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["trip"].queryset = Trip.objects.filter(agency=request.user.agency)
            self.fields["adult_price"].queryset = TripHotelPrice.objects.filter(agency=request.user.agency, scope="TRIP_PACKAGE", passenger_category__code__iexact="adt", price_kind="STANDARD")

    def get_calculated(self, obj):
        from pricing.calculator import calculate_package

        try:
            return calculate_package(obj)
        except DjangoValidationError:
            return None

    def create(self, validated_data):
        return self._save_clean(self.Meta.model(**validated_data))

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        return self._save_clean(instance)


def _passenger_categories(agency):
    return PassengerCategory.objects.filter(Q(is_system=True) | Q(agency=agency), is_active=True)


class PromotionSerializer(CleanModelSerializer):
    trip_name = serializers.CharField(source="trip.name", read_only=True)

    class Meta:
        model = Promotion
        fields = [
            "id",
            "trip",
            "trip_name",
            "code",
            "name",
            "sales_start_date",
            "sales_end_date",
            "description",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            self.fields["trip"].queryset = Trip.objects.filter(agency=request.user.agency)


class TripHotelPriceSerializer(CleanModelSerializer):
    hotel_name = serializers.CharField(source="trip_hotel.hotel.name", read_only=True)
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    passenger_category_name = serializers.CharField(
        source="passenger_category.name", read_only=True
    )
    currency_code = serializers.CharField(source="currency_id", read_only=True)
    promotion_code = serializers.CharField(source="promotion.code", read_only=True)

    class Meta:
        model = TripHotelPrice
        fields = [
            "id",
            "trip_hotel",
            "hotel_name",
            "room_type",
            "room_type_name",
            "passenger_category",
            "passenger_category_name",
            "bed_basis",
            "price_kind",
            "promotion",
            "promotion_code",
            "scope",
            "amount",
            "currency",
            "currency_code",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["trip_hotel"].queryset = TripHotel.objects.filter(stop__trip__agency=agency)
            self.fields["room_type"].queryset = RoomType.objects.filter(agency=agency)
            self.fields["passenger_category"].queryset = _passenger_categories(agency)
            self.fields["promotion"].queryset = Promotion.objects.filter(agency=agency)
            self.fields["currency"].queryset = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )


class SeasonalFlightPriceSerializer(CleanModelSerializer):
    trip_name = serializers.CharField(source="trip.name", read_only=True)
    airline_name = serializers.CharField(source="airline.name", read_only=True)
    passenger_category_name = serializers.CharField(
        source="passenger_category.name", read_only=True
    )
    currency_code = serializers.CharField(source="currency_id", read_only=True)

    class Meta:
        model = SeasonalFlightPrice
        fields = [
            "id",
            "trip",
            "trip_name",
            "fare_name",
            "airline",
            "airline_name",
            "sales_start_date",
            "sales_end_date",
            "passenger_category",
            "passenger_category_name",
            "amount",
            "currency",
            "currency_code",
            "source_reference",
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
            agency = request.user.agency
            self.fields["trip"].queryset = Trip.objects.filter(agency=agency)
            self.fields["airline"].queryset = Airline.objects.filter(is_active=True)
            self.fields["passenger_category"].queryset = _passenger_categories(agency)
            self.fields["currency"].queryset = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )


class QuoteLineSerializer(serializers.ModelSerializer):
    source_currency_code = serializers.CharField(source="source_currency_id", read_only=True)

    class Meta:
        model = QuoteLine
        fields = [
            "id",
            "kind",
            "hotel_price",
            "flight_price",
            "description",
            "quantity",
            "source_unit_amount",
            "source_currency",
            "source_currency_code",
            "exchange_rate",
            "unit_amount",
            "total_amount",
            "source_snapshot",
            "created_at",
        ]
        read_only_fields = fields


class QuoteSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuoteSnapshot
        fields = [
            "sha256",
            "payload",
            "quote_total",
            "quote_currency",
            "accounting_total",
            "accounting_currency",
            "created_at",
        ]
        read_only_fields = fields


class QuoteSerializer(CleanModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)
    trip_name = serializers.CharField(source="trip.name", read_only=True)
    lines = QuoteLineSerializer(many=True, read_only=True)
    snapshot = QuoteSnapshotSerializer(read_only=True)
    total = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)

    class Meta:
        model = Quote
        fields = [
            "id",
            "code",
            "branch",
            "branch_name",
            "customer",
            "customer_name",
            "trip",
            "trip_name",
            "currency",
            "accounting_currency",
            "accounting_exchange_rate",
            "status",
            "valid_until",
            "notes",
            "created_by",
            "issued_at",
            "accepted_at",
            "total",
            "lines",
            "snapshot",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_by",
            "issued_at",
            "accepted_at",
            "total",
            "lines",
            "snapshot",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["branch"].queryset = Branch.objects.filter(agency=agency)
            self.fields["customer"].queryset = Customer.objects.filter(agency=agency)
            self.fields["trip"].queryset = Trip.objects.filter(agency=agency)
            currencies = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )
            self.fields["currency"].queryset = currencies
            self.fields["accounting_currency"].queryset = currencies

    def validate(self, attrs):
        user = self.context["request"].user
        if self.instance and self.instance.status != Quote.Status.DRAFT:
            raise serializers.ValidationError("Issued quotes are immutable.")
        branch = attrs.get("branch", self.instance.branch if self.instance else None)
        if user.branch_id and branch != user.branch:
            raise serializers.ValidationError({"branch": "Branch users must use their branch."})
        currency = attrs.get("currency", self.instance.currency if self.instance else None)
        accounting = attrs.get(
            "accounting_currency", self.instance.accounting_currency if self.instance else None
        )
        rate = attrs.get(
            "accounting_exchange_rate",
            self.instance.accounting_exchange_rate if self.instance else None,
        )
        if currency and accounting and currency == accounting and rate != Decimal("1"):
            raise serializers.ValidationError(
                {"accounting_exchange_rate": "Same-currency rate must equal 1."}
            )
        return attrs


class AddQuotePriceSerializer(serializers.Serializer):
    price_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    exchange_rate = serializers.DecimalField(
        max_digits=18, decimal_places=8, min_value=Decimal("0.00000001"), default=Decimal("1")
    )


class QuoteTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            Quote.Status.ACCEPTED,
            Quote.Status.EXPIRED,
            Quote.Status.CANCELLED,
        ]
    )
