from decimal import Decimal

from django.db.models import Q
from rest_framework import serializers

from bookings.models import (
    Booking,
    BookingAccommodation,
    BookingDiscount,
    BookingFlight,
    BookingRequest,
    BookingRequestAttachment,
    BookingRoomGroup,
    BookingRoomTraveler,
    BookingSnapshot,
    BookingTraveler,
    BookingTravelerCharge,
)
from catalog.models import RoomType
from customers.models import Customer
from organizations.models import Branch
from pricing.models import TripHotelPrice
from reference.models import Currency, PassengerCategory
from travelers.models import Passport, Traveler
from travelers.rules import age_on_date, passenger_category_code, passport_validity
from trips.models import Trip, TripHotel


class BookingRequestAttachmentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = BookingRequestAttachment
        fields = [
            "id", "original_filename", "mime_type", "size_bytes", "download_url", "created_at"
        ]
        read_only_fields = fields

    def get_download_url(self, obj):
        request = self.context.get("request")
        path = f"/api/v1/bookings/requests/{obj.request_id}/attachments/{obj.pk}/download/"
        return request.build_absolute_uri(path) if request else path


class BookingRequestSerializer(serializers.ModelSerializer):
    trip_name = serializers.CharField(source="trip.name", read_only=True)
    package_name = serializers.CharField(source="package.name", read_only=True)
    currency_code = serializers.CharField(source="calculated_currency_id", read_only=True)
    booking_id = serializers.UUIDField(read_only=True)
    attachments = BookingRequestAttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = BookingRequest
        fields = [
            "id",
            "reference",
            "trip",
            "trip_name",
            "customer_name",
            "phone",
            "email",
            "adults",
            "children",
            "children_with_bed",
            "children_without_bed",
            "infants",
            "package",
            "package_name",
            "calculated_total",
            "currency_code",
            "booking_id",
            "pricing_snapshot",
            "attachments",
            "preferred_room_type",
            "notes",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "trip",
            "trip_name",
            "customer_name",
            "phone",
            "email",
            "adults",
            "children",
            "children_with_bed",
            "children_without_bed",
            "infants",
            "package",
            "package_name",
            "calculated_total",
            "currency_code",
            "pricing_snapshot",
            "attachments",
            "preferred_room_type",
            "notes",
            "created_at",
        ]


def traveler_name(traveler):
    passport = next(
        (item for item in traveler.passports.all() if item.status == Passport.Status.CURRENT), None
    )
    if passport:
        return " ".join(part for part in [passport.first_name, passport.last_name] if part)
    name = " ".join(part for part in [traveler.first_name, traveler.last_name] if part)
    return name or f"Traveler {str(traveler.pk)[:8]}"


class BookingTravelerSerializer(serializers.ModelSerializer):
    traveler_name = serializers.SerializerMethodField()
    passenger_category_name = serializers.CharField(
        source="passenger_category.name", read_only=True
    )
    charges = serializers.SerializerMethodField()
    first_name = serializers.CharField(source="traveler.first_name", read_only=True)
    last_name = serializers.CharField(source="traveler.last_name", read_only=True)
    birth_date = serializers.DateField(source="traveler.birth_date", read_only=True)
    gender = serializers.CharField(source="traveler.gender", read_only=True)
    gender_display = serializers.CharField(source="traveler.get_gender_display", read_only=True)
    age_on_return = serializers.SerializerMethodField()
    derived_passenger_category = serializers.SerializerMethodField()
    passport_number = serializers.SerializerMethodField()
    passport_id = serializers.SerializerMethodField()
    passport_expiry_date = serializers.SerializerMethodField()
    passport_validity_status = serializers.SerializerMethodField()
    passport_required_until = serializers.SerializerMethodField()
    passport_is_valid = serializers.SerializerMethodField()
    passport_details = serializers.SerializerMethodField()
    final_amount = serializers.SerializerMethodField()
    room_assignments = serializers.SerializerMethodField()

    class Meta:
        model = BookingTraveler
        fields = [
            "id",
            "traveler",
            "traveler_name",
            "first_name",
            "last_name",
            "passenger_category",
            "passenger_category_name",
            "derived_passenger_category",
            "bed_requirement",
            "seat_required",
            "service_type",
            "included_stops",
            "birth_date",
            "gender",
            "gender_display",
            "age_on_return",
            "passport_number",
            "passport_id",
            "passport_expiry_date",
            "passport_validity_status",
            "passport_required_until",
            "passport_is_valid",
            "passport_details",
            "final_amount",
            "room_assignments",
            "is_customer_contact",
            "notes",
            "charges",
            "added_at",
        ]
        read_only_fields = fields

    def get_traveler_name(self, obj) -> str:
        return traveler_name(obj.traveler)

    def get_charges(self, obj):
        return BookingTravelerChargeSerializer(obj.charges.all(), many=True).data

    def _passport(self, obj):
        return next(
            (
                item
                for item in obj.traveler.passports.all()
                if item.status == Passport.Status.CURRENT
            ),
            None,
        )

    def get_age_on_return(self, obj):
        return (
            age_on_date(obj.traveler.birth_date, obj.booking.trip.return_date)
            if obj.traveler.birth_date
            else None
        )

    def get_derived_passenger_category(self, obj):
        return (
            passenger_category_code(obj.traveler.birth_date, obj.booking.trip.return_date)
            if obj.traveler.birth_date
            else None
        )

    def get_passport_number(self, obj):
        passport = self._passport(obj)
        return passport.passport_number if passport else None

    def get_passport_id(self, obj):
        passport = self._passport(obj)
        return str(passport.pk) if passport else None

    def get_passport_expiry_date(self, obj):
        passport = self._passport(obj)
        return passport.expiry_date if passport else None

    def _validity(self, obj):
        passport = self._passport(obj)
        return passport_validity(
            passport.expiry_date if passport else None, obj.booking.trip.return_date
        )

    def get_passport_validity_status(self, obj):
        return self._validity(obj).status

    def get_passport_required_until(self, obj):
        return self._validity(obj).required_until

    def get_passport_is_valid(self, obj):
        return self._validity(obj).is_valid

    def get_passport_details(self, obj):
        passport = self._passport(obj)
        if passport is None:
            return None
        return {
            "passport_number": passport.passport_number,
            "first_name": passport.first_name,
            "middle_name": passport.middle_name,
            "last_name": passport.last_name,
            "birth_date": passport.birth_date,
            "gender": passport.gender,
            "nationality": str(passport.nationality_id),
            "issuing_country": str(passport.issuing_country_id),
            "birth_country": str(passport.birth_country_id or ""),
            "birth_place": passport.birth_place,
            "issue_date": passport.issue_date,
            "expiry_date": passport.expiry_date,
            "issue_place": passport.issue_place,
            "mrz": passport.mrz,
        }

    def get_final_amount(self, obj):
        return sum((item.final_amount for item in obj.charges.all()), Decimal("0"))

    def get_room_assignments(self, obj):
        actual = list(obj.trip_room_assignments.all())
        stops = {link.stop_id for link in actual}
        return [{"id": str(link.pk), "room_group": None, "room": str(link.room_id), "hotel": link.room.trip_hotel.hotel.name, "city": link.room.trip_hotel.stop.city.name, "room_type": link.room.room_type.name, "label": link.room.label} for link in actual] + [
            {
                "id": str(link.pk),
                "room_group": str(link.room_group_id),
                "hotel": link.room_group.trip_hotel.hotel.name,
                "city": link.room_group.trip_hotel.stop.city.name,
                "room_type": link.room_group.room_type.name,
                "label": link.room_group.label,
            }
            for link in obj.room_assignments.all()
            if link.room_group.trip_hotel.stop_id not in stops
        ]


class BookingAccommodationSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="trip_hotel.hotel.name", read_only=True)
    city_name = serializers.CharField(source="trip_hotel.stop.city.name", read_only=True)
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    passenger_category_name = serializers.CharField(
        source="passenger_category.name", read_only=True
    )
    currency_code = serializers.CharField(source="currency_id", read_only=True)

    class Meta:
        model = BookingAccommodation
        fields = [
            "id",
            "trip_hotel",
            "hotel_name",
            "city_name",
            "room_type",
            "room_type_name",
            "passenger_category",
            "passenger_category_name",
            "bed_basis",
            "quantity",
            "unit_amount",
            "total_amount",
            "currency",
            "currency_code",
            "source_quote_line",
        ]
        read_only_fields = fields


class BookingFlightSerializer(serializers.ModelSerializer):
    flight_number = serializers.CharField(source="trip_flight.flight_number", read_only=True)
    direction = serializers.CharField(source="trip_flight.direction", read_only=True)
    origin_airport_code = serializers.CharField(
        source="trip_flight.origin_airport_code", read_only=True
    )
    destination_airport_code = serializers.CharField(
        source="trip_flight.destination_airport_code", read_only=True
    )
    departure_at = serializers.DateTimeField(source="trip_flight.departure_at", read_only=True)
    arrival_at = serializers.DateTimeField(source="trip_flight.arrival_at", read_only=True)

    class Meta:
        model = BookingFlight
        fields = [
            "id",
            "trip_flight",
            "flight_number",
            "direction",
            "origin_airport_code",
            "destination_airport_code",
            "departure_at",
            "arrival_at",
        ]
        read_only_fields = fields


class BookingSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingSnapshot
        fields = ["sha256", "payload", "created_at"]
        read_only_fields = fields


class BookingDiscountSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingDiscount
        fields = ["id", "kind", "value", "amount", "reason", "created_at"]
        read_only_fields = fields


class BookingTravelerChargeSerializer(serializers.ModelSerializer):
    discount_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    final_amount = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    currency_code = serializers.CharField(source="currency_id", read_only=True)
    discounts = BookingDiscountSerializer(many=True, read_only=True)

    class Meta:
        model = BookingTravelerCharge
        fields = [
            "id",
            "kind",
            "description",
            "source_price",
            "base_amount",
            "discount_amount",
            "final_amount",
            "currency",
            "currency_code",
            "notes",
            "discounts",
        ]
        read_only_fields = fields


class BookingRoomTravelerSerializer(serializers.ModelSerializer):
    traveler_name = serializers.SerializerMethodField()

    class Meta:
        model = BookingRoomTraveler
        fields = ["id", "booking_traveler", "traveler_name"]
        read_only_fields = fields

    def get_traveler_name(self, obj):
        return traveler_name(obj.booking_traveler.traveler)


class BookingRoomGroupSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="trip_hotel.hotel.name", read_only=True)
    city_name = serializers.CharField(source="trip_hotel.stop.city.name", read_only=True)
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    traveler_assignments = BookingRoomTravelerSerializer(many=True, read_only=True)

    class Meta:
        model = BookingRoomGroup
        fields = [
            "id",
            "trip_hotel",
            "hotel_name",
            "city_name",
            "room_type",
            "room_type_name",
            "label",
            "capacity",
            "notes",
            "traveler_assignments",
        ]
        read_only_fields = fields


class BookingSerializer(serializers.ModelSerializer):
    offer_revision = serializers.SerializerMethodField()

    def get_offer_revision(self, obj):
        from bookings.commercial import offer_revision
        return offer_revision(obj) if obj.status == 'DRAFT' else None
    partner_name = serializers.CharField(source="partner.name", read_only=True, default=None)
    agency_name = serializers.CharField(source="agency.legal_name", read_only=True)
    agency_logo = serializers.ImageField(source="agency.logo", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    customer_name = serializers.CharField(source="customer.display_name", read_only=True)
    trip_name = serializers.CharField(source="trip.name", read_only=True)
    source_quote_code = serializers.SerializerMethodField()
    currency_code = serializers.CharField(source="currency_id", read_only=True)
    accounting_currency_code = serializers.CharField(
        source="accounting_currency_id", read_only=True
    )
    travelers = BookingTravelerSerializer(many=True, read_only=True)
    accommodations = BookingAccommodationSerializer(many=True, read_only=True)
    flights = BookingFlightSerializer(many=True, read_only=True)
    snapshot = BookingSnapshotSerializer(read_only=True)
    traveler_count = serializers.IntegerField(read_only=True, default=0)
    capacity = serializers.SerializerMethodField()
    room_groups = BookingRoomGroupSerializer(many=True, read_only=True)
    customer_phone = serializers.CharField(source="customer.phone", read_only=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    customer_first_name = serializers.CharField(source="customer.first_name", read_only=True)
    customer_last_name = serializers.CharField(source="customer.last_name", read_only=True)
    customer_address = serializers.CharField(source="customer.address", read_only=True)
    return_date = serializers.DateField(source="trip.return_date", read_only=True)
    readiness = serializers.SerializerMethodField()
    paid_amount = serializers.SerializerMethodField()
    remaining_amount = serializers.SerializerMethodField()

    def get_source_quote_code(self, obj):
        return obj.source_quote.code if obj.source_quote_id else ""

    def get_paid_amount(self, obj):
        if not hasattr(obj, "_serialized_paid_amount"):
            obj._serialized_paid_amount = sum(
                (entry.signed_booking_amount for entry in obj.financial_transactions.all()),
                Decimal("0"),
            )
        return obj._serialized_paid_amount

    def get_remaining_amount(self, obj):
        return obj.total_amount - self.get_paid_amount(obj)

    class Meta:
        model = Booking
        fields = [
            "id",
            "code",
            "agency_name",
            "agency_logo",
            "partner",
            "partner_name",
            "commercial_details",
            "offer_revision",
            "branch",
            "branch_name",
            "customer",
            "customer_name",
            "customer_phone",
            "customer_email",
            "customer_first_name",
            "customer_last_name",
            "customer_address",
            "trip",
            "trip_name",
            "return_date",
            "source_quote",
            "source_quote_code",
            "currency",
            "currency_code",
            "total_amount",
            "paid_amount",
            "remaining_amount",
            "accounting_currency",
            "accounting_currency_code",
            "accounting_exchange_rate",
            "accounting_total_amount",
            "status",
            "notes",
            "cancellation_reason",
            "cancelled_at",
            "completed_at",
            "expected_travelers",
            "capacity",
            "traveler_count",
            "travelers",
            "accommodations",
            "room_groups",
            "readiness",
            "flights",
            "snapshot",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_capacity(self, obj):
        from bookings.readiness import booking_capacity
        return booking_capacity(obj)

    def get_readiness(self, obj):
        from bookings.readiness import booking_readiness
        result = booking_readiness(obj)
        rows = result["travelers_detail"]
        required = result["required_room_assignments"]
        completed = result["completed_room_assignments"]
        capacity = self.get_capacity(obj)
        commercial = result["commercial_ready"] and capacity["has_capacity"]
        return {
            "structured": result,
            "expected_travelers": obj.expected_travelers,
            "traveler_count": result["travelers"]["total"],
            "remaining_travelers": max(obj.expected_travelers - len(rows), 0),
            "validated_travelers": sum(row["fields"]["identity"] == "VALID" and row["fields"]["price"] == "VALID" for row in rows),
            "contact_complete": result["contact_complete"],
            "missing_passports": result["missing"]["passport"],
            "invalid_passports": result["invalid"]["passport"],
            "missing_prices": result["missing"]["price"],
            "missing_rooms": required - completed,
            "price_category_mismatches": sum("Price category does not match traveler" in row["issues"] for row in rows),
            "required_room_assignments": required,
            "completed_room_assignments": completed,
            "allocation_status": "NOT_REQUIRED" if not required else "COMPLETE" if completed == required else "PARTIAL" if completed else "NOT_STARTED",
            "completion": [{"id": row["id"], "issues": row["issues"]} for row in rows],
            "traveler_validation": [{"id": row["id"], "name": row["name"], "issues": row["issues"]} for row in rows],
            "payment_blockers": (["Add all requested travelers and their valid passports before taking payment."] if len(rows) != obj.expected_travelers else [row["name"] + ": valid passport required" for row in rows if row["fields"]["passport"] != "VALID"]),
            "commercial_ready": commercial,
            "operational_ready": result["is_ready"] and capacity["has_capacity"],
            "is_ready": result["is_ready"] and capacity["has_capacity"],
        }


class BookingFromQuoteSerializer(serializers.Serializer):
    quote_id = serializers.UUIDField()
    code = serializers.SlugField(max_length=70, required=False, allow_blank=True, default="")


class DirectBookingPriceSerializer(serializers.Serializer):
    price_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    exchange_rate = serializers.DecimalField(
        max_digits=18, decimal_places=8, min_value=Decimal("0.00000001")
    )


class InlineCustomerSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=Customer.Kind.choices, default=Customer.Kind.INDIVIDUAL)
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    company_name = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if attrs["kind"] == Customer.Kind.COMPANY and not attrs["company_name"].strip():
            raise serializers.ValidationError({"company_name": "Company name is required."})
        if attrs["kind"] == Customer.Kind.INDIVIDUAL and not (
            attrs["first_name"].strip() or attrs["last_name"].strip()
        ):
            raise serializers.ValidationError("Enter at least a first or last name.")
        if not (attrs["phone"].strip() or attrs["email"].strip()):
            raise serializers.ValidationError(
                "Enter a phone number or email so the agency can contact the customer."
            )
        return attrs


class DirectBookingSerializer(serializers.Serializer):
    code = serializers.SlugField(max_length=70, required=False, allow_blank=True, default="")
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none())
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.none(), required=False, allow_null=True
    )
    new_customer = InlineCustomerSerializer(required=False)
    trip = serializers.PrimaryKeyRelatedField(queryset=Trip.objects.none())
    currency = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.none())
    accounting_currency = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.none())
    accounting_exchange_rate = serializers.DecimalField(
        max_digits=18, decimal_places=8, min_value=Decimal("0.00000001")
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    price_lines = DirectBookingPriceSerializer(many=True, allow_empty=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["branch"].queryset = Branch.objects.filter(agency=agency)
            self.fields["customer"].queryset = Customer.objects.filter(
                agency=agency, is_active=True
            )
            self.fields["trip"].queryset = Trip.objects.filter(agency=agency)
            currencies = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )
            self.fields["currency"].queryset = currencies
            self.fields["accounting_currency"].queryset = currencies

    def validate_price_lines(self, value):
        ids = [str(line["price_id"]) for line in value]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Each hotel price may be selected only once.")
        return value

    def validate(self, attrs):
        if bool(attrs.get("customer")) == bool(attrs.get("new_customer")):
            raise serializers.ValidationError(
                "Select an existing customer or enter a new customer, but not both."
            )
        return attrs


class BookingDraftSerializer(DirectBookingSerializer):
    lead_source = serializers.ChoiceField(choices=['WALK_IN', 'SOCIAL_MEDIA', 'PARTNER', 'REFERRER', 'OTHER'], required=False)
    source_detail = serializers.CharField(max_length=250, allow_blank=True, default='')
    from partners.models import Partner
    partner = serializers.PrimaryKeyRelatedField(queryset=Partner.objects.none(), required=False)
    expected_travelers = serializers.IntegerField(min_value=1, max_value=32767, default=1)
    code = None
    price_lines = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            partners = self.Partner.objects.filter(agency=request.user.agency, is_active=True, kind="COMPANY")
            if request.user.branch_id and not request.user.has_perm("partners.view_all_partners"):
                partners = partners.filter(branch=request.user.branch)
            self.fields["partner"].queryset = partners

    def validate(self, attrs):
        if attrs.get("partner"):
            if attrs.get("customer") or attrs.get("new_customer"):
                raise serializers.ValidationError("Choose a partner or a customer, not both.")
            return attrs
        return super().validate(attrs)


class InlineBookingTravelerSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, default="")
    last_name = serializers.CharField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    birth_date = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=Traveler.Gender.choices, default="X")
    passenger_category = serializers.PrimaryKeyRelatedField(
        queryset=PassengerCategory.objects.none(), required=False, allow_null=True
    )
    bed_requirement = serializers.ChoiceField(choices=BookingTraveler.BedRequirement.choices)
    is_customer_contact = serializers.BooleanField(default=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["passenger_category"].queryset = PassengerCategory.objects.filter(
                Q(is_system=True) | Q(agency=agency), is_active=True
            )


class MrzInputSerializer(serializers.Serializer):
    mrz = serializers.CharField(allow_blank=False)


class BookingCustomerContactSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    phone = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        customer = self.context["customer"]
        phone = attrs.get("phone", customer.phone)
        email = attrs.get("email", customer.email)
        if not (phone.strip() or email.strip()):
            raise serializers.ValidationError("Enter a phone number or email.")
        return attrs


class AddRoomGroupSerializer(serializers.Serializer):
    trip_hotel = serializers.PrimaryKeyRelatedField(queryset=TripHotel.objects.none())
    room_type = serializers.PrimaryKeyRelatedField(queryset=RoomType.objects.none())
    label = serializers.CharField(max_length=80)
    capacity = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["trip_hotel"].queryset = TripHotel.objects.filter(stop__trip__agency=agency)
            self.fields["room_type"].queryset = RoomType.objects.filter(
                agency=agency, is_active=True
            )


class AssignRoomTravelerSerializer(serializers.Serializer):
    booking_traveler_id = serializers.UUIDField()


class AddTravelerChargeSerializer(serializers.Serializer):
    booking_traveler_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=BookingTravelerCharge.Kind.choices)
    description = serializers.CharField(max_length=180)
    source_price = serializers.PrimaryKeyRelatedField(
        queryset=TripHotelPrice.objects.none(), required=False, allow_null=True
    )
    base_amount = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0"))
    currency = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.none())
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            self.fields["source_price"].queryset = TripHotelPrice.objects.filter(agency=agency)
            self.fields["currency"].queryset = Currency.objects.filter(
                agency_settings__agency=agency, agency_settings__is_enabled=True
            )


class AddChargeDiscountSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=BookingDiscount.Kind.choices)
    value = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    reason = serializers.CharField(max_length=240)


class AddBookingTravelerSerializer(serializers.Serializer):
    traveler = serializers.PrimaryKeyRelatedField(queryset=Traveler.objects.none())
    passenger_category = serializers.PrimaryKeyRelatedField(
        queryset=PassengerCategory.objects.none()
    )
    bed_requirement = serializers.ChoiceField(choices=BookingTraveler.BedRequirement.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            agency = request.user.agency
            travelers = Traveler.objects.filter(agency=agency, is_active=True)
            if request.user.branch_id and not request.user.has_perm("travelers.view_all_travelers"):
                travelers = travelers.filter(branch=request.user.branch)
            self.fields["traveler"].queryset = travelers
            self.fields["passenger_category"].queryset = PassengerCategory.objects.filter(
                Q(is_system=True) | Q(agency=agency), is_active=True
            )


class BookingTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=[Booking.Status.CANCELLED, Booking.Status.COMPLETED])
    cancellation_reason = serializers.CharField(required=False, allow_blank=True, default="")
