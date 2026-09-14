from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from bookings.models import BookingTraveler
from catalog.models import Airline, Hotel, RoomType, Supplier
from organizations.models import Branch
from reference.models import City
from trips.models import (
    Trip,
    TripAllocationRoom,
    TripClosingItem,
    TripFlight,
    TripHotel,
    TripRoomAssignment,
    TripStop,
    TripTransport,
)
from trips.services import save_trip_stop


class TripSerializer(serializers.ModelSerializer):
    agency_name = serializers.CharField(source="agency.name", read_only=True)
    agency_logo = serializers.ImageField(source="agency.logo", read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    stop_count = serializers.IntegerField(read_only=True, default=0)
    hotel_count = serializers.IntegerField(read_only=True, default=0)
    flight_count = serializers.IntegerField(read_only=True, default=0)
    booked_places = serializers.SerializerMethodField()
    capacity_summary = serializers.SerializerMethodField()
    remaining_places = serializers.SerializerMethodField()

    def get_capacity_summary(self, obj):
        from bookings.readiness import seat_summary
        if not hasattr(obj, "_seats"):
            obj._seats = seat_summary(obj)
        return obj._seats

    def get_booked_places(self, obj):
        return self.get_capacity_summary(obj)["occupied"]

    def get_remaining_places(self, obj):
        return self.get_capacity_summary(obj)["remaining"]

    class Meta:
        model = Trip
        fields = [
            "id",
            "agency_name",
            "agency_logo",
            "code",
            "name",
            "branch",
            "branch_name",
            "departure_date",
            "return_date",
            "pricing_currency",
            "child_with_bed_discount",
            "child_without_bed_price",
            "infant_price",
            "booking_open_date",
            "booking_close_date",
            "max_travelers",
            "status",
            "description",
            "notes",
            "closing_status",
            "closing_started_at",
            "closed_at",
            "closed_by",
            "stop_count",
            "hotel_count",
            "flight_count",
            "booked_places",
            "capacity_summary",
            "remaining_places",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "stop_count",
            "hotel_count",
            "flight_count",
            "created_at",
            "updated_at",
            "closing_status",
            "closing_started_at",
            "closed_at",
            "closed_by",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["branch"].queryset = Branch.objects.filter(agency=request.user.agency)
            self.fields["branch"].required = not bool(request.user.branch_id)

    def validate(self, attrs):
        user = self.context["request"].user
        if self.instance is None and "branch" not in attrs:
            if user.branch_id:
                attrs["branch"] = user.branch
            else:
                raise serializers.ValidationError({"branch": "A managing branch is required."})
        branch = attrs.get("branch", self.instance.branch if self.instance else None)
        if user.branch_id and branch != user.branch:
            raise serializers.ValidationError({"branch": "Branch users must use their own branch."})
        departure = attrs.get(
            "departure_date", self.instance.departure_date if self.instance else None
        )
        returning = attrs.get("return_date", self.instance.return_date if self.instance else None)
        if departure and returning and returning < departure:
            raise serializers.ValidationError({"return_date": "Return cannot precede departure."})
        booking_open = attrs.get(
            "booking_open_date", self.instance.booking_open_date if self.instance else None
        )
        booking_close = attrs.get(
            "booking_close_date", self.instance.booking_close_date if self.instance else None
        )
        if booking_open and booking_close and booking_close < booking_open:
            raise serializers.ValidationError({"booking_close_date": "Invalid booking window."})
        if booking_close and departure and booking_close > departure:
            raise serializers.ValidationError(
                {"booking_close_date": "Bookings must close by departure."}
            )
        return attrs


class TripStopSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source="city.name", read_only=True)
    country_code = serializers.CharField(source="city.country.code", read_only=True)
    nights = serializers.IntegerField(read_only=True)

    class Meta:
        model = TripStop
        fields = [
            "id",
            "trip",
            "city",
            "city_name",
            "country_code",
            "arrival_date",
            "departure_date",
            "nights",
            "order",
            "notes",
        ]
        read_only_fields = ["id", "nights"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["trip"].queryset = Trip.objects.filter(agency=request.user.agency)
        self.fields["city"].queryset = City.objects.select_related("country")

    def create(self, validated_data):
        try:
            return save_trip_stop(**validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def update(self, instance, validated_data):
        trip = validated_data.pop("trip", instance.trip)
        try:
            return save_trip_stop(instance=instance, trip=trip, **validated_data)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class TripHotelSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel.name", read_only=True)
    city_name = serializers.CharField(source="stop.city.name", read_only=True)

    class Meta:
        model = TripHotel
        fields = ["id", "stop", "hotel", "hotel_name", "city_name", "is_primary", "notes"]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["stop"].queryset = TripStop.objects.filter(trip__agency=request.user.agency)
            self.fields["hotel"].queryset = Hotel.objects.filter(agency=request.user.agency)

    def validate(self, attrs):
        stop = attrs.get("stop", self.instance.stop if self.instance else None)
        hotel = attrs.get("hotel", self.instance.hotel if self.instance else None)
        if stop and hotel and hotel.city_id != stop.city_id:
            raise serializers.ValidationError(
                {"hotel": "Hotel must be in the itinerary stop city."}
            )
        is_primary = attrs.get("is_primary", self.instance.is_primary if self.instance else False)
        if stop and is_primary:
            existing = TripHotel.objects.filter(stop=stop, is_primary=True)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError("This stop already has a primary hotel.")
        return attrs


class TripRoomAssignmentSerializer(serializers.ModelSerializer):
    traveler_name = serializers.CharField(
        source="booking_traveler.traveler.display_name", read_only=True
    )
    booking_code = serializers.CharField(source="booking_traveler.booking.code", read_only=True)
    gender = serializers.CharField(source="booking_traveler.traveler.gender", read_only=True)
    traveler_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = TripRoomAssignment
        fields = [
            "id",
            "stop",
            "room",
            "booking_traveler",
            "traveler_name",
            "booking_code",
            "gender",
            "traveler_photo_url",
            "bed_number",
        ]
        read_only_fields = fields

    def get_traveler_photo_url(self, obj):
        photo = obj.booking_traveler.traveler.current_photo_id
        if not photo:
            return None
        request = self.context.get("request")
        path = f"/api/v1/documents/{photo}/download/"
        return request.build_absolute_uri(path) if request else path


class TripAllocationRoomSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="trip_hotel.hotel.name", read_only=True)
    city_name = serializers.CharField(source="trip_hotel.stop.city.name", read_only=True)
    stop = serializers.UUIDField(source="trip_hotel.stop_id", read_only=True)
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    capacity = serializers.IntegerField(read_only=True)
    assignments = TripRoomAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = TripAllocationRoom
        fields = [
            "id",
            "trip_hotel",
            "hotel_name",
            "city_name",
            "stop",
            "room_type",
            "room_type_name",
            "label",
            "actual_room_number",
            "standard_beds",
            "extra_beds",
            "capacity",
            "occupancy_policy",
            "notes",
            "assignments",
        ]
        read_only_fields = ["id", "hotel_name", "city_name", "stop", "capacity", "assignments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            agency = request.user.agency
            self.fields["trip_hotel"].queryset = TripHotel.objects.filter(stop__trip__agency=agency)
            self.fields["room_type"].queryset = RoomType.objects.filter(
                agency=agency, is_active=True
            )

    def validate(self, attrs):
        trip_hotel = attrs.get("trip_hotel", self.instance.trip_hotel if self.instance else None)
        room_type = attrs.get("room_type", self.instance.room_type if self.instance else None)
        standard_beds = attrs.get(
            "standard_beds", self.instance.standard_beds if self.instance else None
        )
        extra_beds = attrs.get("extra_beds", self.instance.extra_beds if self.instance else 0)
        if trip_hotel and room_type and room_type.agency_id != trip_hotel.stop.trip.agency_id:
            raise serializers.ValidationError("Room type must belong to the trip agency.")
        if self.instance and self.instance.assignments.exists():
            highest_bed = max(
                self.instance.assignments.values_list("bed_number", flat=True), default=0
            )
            if standard_beds + extra_beds < highest_bed:
                raise serializers.ValidationError(
                    "Capacity cannot be reduced below an occupied bed position."
                )
        return attrs


class RoomAssignmentInputSerializer(serializers.Serializer):
    booking_traveler = serializers.PrimaryKeyRelatedField(queryset=BookingTraveler.objects.none())
    bed_number = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["booking_traveler"].queryset = BookingTraveler.objects.filter(
                booking__agency=request.user.agency,
                booking__status__in=["CONFIRMED", "COMPLETED"],
            )


class TripFlightSerializer(serializers.ModelSerializer):
    airline_name = serializers.CharField(source="airline.name", read_only=True)
    origin_city_name = serializers.CharField(source="origin_city.name", read_only=True)
    destination_city_name = serializers.CharField(source="destination_city.name", read_only=True)

    class Meta:
        model = TripFlight
        fields = [
            "id",
            "trip",
            "airline",
            "airline_name",
            "direction",
            "flight_number",
            "origin_city",
            "origin_city_name",
            "destination_city",
            "destination_city_name",
            "origin_airport_code",
            "destination_airport_code",
            "departure_at",
            "arrival_at",
            "booking_class",
            "order",
            "notes",
        ]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["trip"].queryset = Trip.objects.filter(agency=request.user.agency)
        self.fields["airline"].queryset = Airline.objects.filter(is_active=True)
        city_queryset = City.objects.select_related("country")
        self.fields["origin_city"].queryset = city_queryset
        self.fields["destination_city"].queryset = city_queryset

    def validate(self, attrs):
        departure = attrs.get("departure_at", self.instance.departure_at if self.instance else None)
        arrival = attrs.get("arrival_at", self.instance.arrival_at if self.instance else None)
        origin = attrs.get("origin_city", self.instance.origin_city if self.instance else None)
        destination = attrs.get(
            "destination_city", self.instance.destination_city if self.instance else None
        )
        if departure and arrival and arrival <= departure:
            raise serializers.ValidationError({"arrival_at": "Arrival must be after departure."})
        if origin and destination and origin == destination:
            raise serializers.ValidationError({"destination_city": "Flight cities must differ."})
        return attrs


class TripTransportSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    origin_city_name = serializers.CharField(source="origin_city.name", read_only=True)
    destination_city_name = serializers.CharField(source="destination_city.name", read_only=True)
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    trip_code = serializers.CharField(source="trip.code", read_only=True)
    trip_name = serializers.CharField(source="trip.name", read_only=True)
    passenger_count = serializers.SerializerMethodField()

    class Meta:
        model = TripTransport
        fields = [
            "id",
            "trip",
            "mode",
            "mode_display",
            "supplier",
            "supplier_name",
            "origin_city",
            "origin_city_name",
            "destination_city",
            "destination_city_name",
            "departure_at",
            "arrival_at",
            "reference",
            "vehicle_details",
            "vehicle_number",
            "order",
            "notes",
            "trip_code",
            "trip_name",
            "passenger_count",
        ]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["trip"].queryset = Trip.objects.filter(agency=request.user.agency)
            self.fields["supplier"].queryset = Supplier.objects.filter(
                agency=request.user.agency, is_active=True
            )
        city_queryset = City.objects.select_related("country")
        self.fields["origin_city"].queryset = city_queryset
        self.fields["destination_city"].queryset = city_queryset

    def get_passenger_count(self, obj):
        if hasattr(obj, "passenger_count"):
            return obj.passenger_count
        return obj.trip.bookings.filter(
            status__in=["CONFIRMED", "COMPLETED"]
        ).values_list("travelers__pk", flat=True).distinct().count()

    def validate(self, attrs):
        departure = attrs.get("departure_at", self.instance.departure_at if self.instance else None)
        arrival = attrs.get("arrival_at", self.instance.arrival_at if self.instance else None)
        origin = attrs.get("origin_city", self.instance.origin_city if self.instance else None)
        destination = attrs.get(
            "destination_city", self.instance.destination_city if self.instance else None
        )
        trip = attrs.get("trip", self.instance.trip if self.instance else None)
        supplier = attrs.get("supplier", self.instance.supplier if self.instance else None)
        if departure and arrival and arrival <= departure:
            raise serializers.ValidationError({"arrival_at": "Arrival must be after departure."})
        if origin and destination and origin == destination:
            raise serializers.ValidationError({"destination_city": "Transport cities must differ."})
        if supplier and trip and supplier.agency_id != trip.agency_id:
            raise serializers.ValidationError(
                {"supplier": "Supplier must belong to the trip agency."}
            )
        return attrs


class TripTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Trip.Status.choices)


class StopReorderSerializer(serializers.Serializer):
    stop_ids = serializers.ListField(child=serializers.UUIDField(), allow_empty=False)


class TripClosingItemSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="get_key_display", read_only=True)
    completed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = TripClosingItem
        fields = [
            "id",
            "key",
            "label",
            "state",
            "notes",
            "assigned_to",
            "due_date",
            "completed_by_name",
            "completed_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_completed_by_name(self, obj):
        if not obj.completed_by_id:
            return ""
        return obj.completed_by.get_full_name() or obj.completed_by.email


class TripClosingItemUpdateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=TripClosingItem.State.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    assigned_to = serializers.UUIDField(required=False, allow_null=True, default=None)
    due_date = serializers.DateField(required=False, allow_null=True, default=None)
