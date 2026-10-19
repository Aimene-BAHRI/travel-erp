import re
from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
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
    code = serializers.CharField(required=False, allow_blank=True)
    name = serializers.CharField(required=False, allow_blank=True)
    trip_hotel = serializers.PrimaryKeyRelatedField(
        queryset=TripHotel.objects.none(), write_only=True, required=False
    )
    room_type = serializers.PrimaryKeyRelatedField(
        queryset=RoomType.objects.none(), write_only=True, required=False
    )
    adult_amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), write_only=True, required=False
    )
    currency = serializers.PrimaryKeyRelatedField(
        queryset=Currency.objects.none(), write_only=True, required=False
    )
    def validate(self, attrs):
        trip = attrs.get("trip", self.instance.trip if self.instance else None)
        adult_price = attrs.get("adult_price")
        trip_hotel = attrs.get("trip_hotel")
        room_type = attrs.get("room_type")
        adult_amount = attrs.get("adult_amount")
        currency = attrs.get("currency")
        if not adult_price and self.instance:
            adult_price = self.instance.adult_price
        if not adult_price and not all((trip_hotel, room_type, adult_amount, currency)):
            raise serializers.ValidationError({"trip_hotel": "Choose a hotel, room, adult price, and currency."})
        if trip_hotel and trip and trip.pricing_currency_id and currency and trip.pricing_currency_id != currency.pk:
            raise serializers.ValidationError({"currency": "Package hotel prices must use the trip pricing currency."})
        if trip_hotel and trip and trip_hotel.stop.trip_id != trip.pk:
            raise serializers.ValidationError({"trip_hotel": "Select a hotel from this trip."})
        if room_type and trip and room_type.agency_id != trip.agency_id:
            raise serializers.ValidationError({"room_type": "Select a room type from this agency."})
        if adult_price and trip and adult_price.trip_hotel.stop.trip_id != trip.pk:
            raise serializers.ValidationError({"adult_price": "Select an adult price from this trip."})
        return super().validate(attrs)

    class Meta:
        model = TripOccupancyPackage
        fields = [
            "id",
            "trip",
            "adult_price",
            "trip_hotel",
            "room_type",
            "adult_amount",
            "currency",
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
            self.fields["trip_hotel"].queryset = TripHotel.objects.filter(stop__trip__agency=request.user.agency)
            self.fields["room_type"].queryset = RoomType.objects.filter(agency=request.user.agency, is_active=True)
            self.fields["currency"].queryset = Currency.objects.filter(agency_settings__agency=request.user.agency, agency_settings__is_enabled=True)

    def get_calculated(self, obj):
        from pricing.calculator import calculate_package

        try:
            return calculate_package(obj)
        except DjangoValidationError:
            return None

    def _resolve_adult_price(self, validated_data):
        trip_hotel = validated_data.pop("trip_hotel", None)
        room_type = validated_data.pop("room_type", None)
        adult_amount = validated_data.pop("adult_amount", None)
        currency = validated_data.pop("currency", None)
        if not trip_hotel:
            return validated_data.pop("adult_price", None)
        if room_type is None or adult_amount is None or currency is None:
            raise serializers.ValidationError({"trip_hotel": "Choose a hotel, room, adult price, and currency."})
        from reference.models import PassengerCategory

        adult = PassengerCategory.objects.get(code__iexact="ADT", is_system=True, is_active=True)
        price, _ = TripHotelPrice.objects.get_or_create(
            agency=validated_data["trip"].agency,
            trip_hotel=trip_hotel,
            room_type=room_type,
            passenger_category=adult,
            bed_basis=TripHotelPrice.BedBasis.STANDARD,
            price_kind=TripHotelPrice.PriceKind.STANDARD,
            scope="TRIP_PACKAGE",
            defaults={"amount": adult_amount, "currency": currency},
        )
        if price.amount != adult_amount or price.currency_id != currency.pk:
            price.amount = adult_amount
            price.currency = currency
            price.full_clean()
            price.save(update_fields=["amount", "currency", "updated_at"])
        validated_data["adult_price"] = price
        return validated_data

    @staticmethod
    def _generated_identity(trip_hotel, room_type, trip, current=None):
        hotel_name = trip_hotel.hotel.name
        name = f"{hotel_name} / {room_type.name}"[:80]
        base = re.sub(r"[^a-z0-9]+", "-", f"{hotel_name}-{room_type.name}".lower()).strip("-")[:24] or "package"
        existing = TripOccupancyPackage.objects.filter(trip=trip, code__startswith=base)
        if current:
            existing = existing.exclude(pk=current.pk)
        used = set(existing.values_list("code", flat=True))
        code = base
        suffix = 2
        while code in used:
            tail = f"-{suffix}"
            code = f"{base[:30-len(tail)]}{tail}"
            suffix += 1
        return code, name

    @transaction.atomic
    def create(self, validated_data):
        trip_hotel = validated_data.get("trip_hotel")
        room_type = validated_data.get("room_type")
        trip = validated_data.get("trip")
        validated_data = self._resolve_adult_price(validated_data)
        if trip_hotel and room_type and trip:
            validated_data["code"], validated_data["name"] = self._generated_identity(trip_hotel, room_type, trip)
        return self._save_clean(self.Meta.model(**validated_data))

    @transaction.atomic
    def update(self, instance, validated_data):
        validated_data.setdefault("trip", instance.trip)
        selected_price = validated_data.get("adult_price", instance.adult_price)
        trip_hotel = validated_data.get("trip_hotel") or (selected_price.trip_hotel if selected_price else None)
        room_type = validated_data.get("room_type") or (selected_price.room_type if selected_price else None)
        if trip_hotel and room_type and "adult_amount" not in validated_data:
            validated_data["trip_hotel"] = trip_hotel
            validated_data["room_type"] = room_type
            validated_data["adult_amount"] = selected_price.amount
            validated_data["currency"] = selected_price.currency
        self._resolve_adult_price(validated_data)
        if trip_hotel and room_type:
            validated_data["code"], validated_data["name"] = self._generated_identity(trip_hotel, room_type, instance.trip, instance)
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
    passenger_category_code = serializers.CharField(source="passenger_category.code", read_only=True)
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
            "passenger_category_code",
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
