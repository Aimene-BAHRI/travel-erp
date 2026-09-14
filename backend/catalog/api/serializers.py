from rest_framework import serializers

from catalog.models import Airline, Hotel, Room, RoomType, Supplier
from reference.models import City


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "legal_name",
            "registration_number",
            "tax_number",
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


class AirlineSerializer(serializers.ModelSerializer):
    country_code = serializers.CharField(source="country.code", read_only=True)

    class Meta:
        model = Airline
        fields = ["id", "name", "iata_code", "icao_code", "country", "country_code", "is_active"]


class HotelSerializer(serializers.ModelSerializer):
    city_name = serializers.CharField(source="city.name", read_only=True)
    country_code = serializers.CharField(source="city.country.code", read_only=True)
    room_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Hotel
        fields = [
            "id",
            "name",
            "city",
            "city_name",
            "country_code",
            "star_rating",
            "address",
            "phone",
            "email",
            "website",
            "check_in_time",
            "check_out_time",
            "notes",
            "is_active",
            "room_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "room_count", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["city"].queryset = City.objects.select_related("country")


class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = [
            "id",
            "code",
            "name",
            "default_standard_beds",
            "description",
            "is_active",
            "sort_order",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class RoomSerializer(serializers.ModelSerializer):
    hotel_name = serializers.CharField(source="hotel.name", read_only=True)
    room_type_name = serializers.CharField(source="room_type.name", read_only=True)
    maximum_beds = serializers.IntegerField(read_only=True)

    class Meta:
        model = Room
        fields = [
            "id",
            "hotel",
            "hotel_name",
            "room_type",
            "room_type_name",
            "number",
            "floor",
            "standard_beds",
            "max_extra_beds",
            "maximum_beds",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "maximum_beds", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["hotel"].queryset = Hotel.objects.filter(agency=request.user.agency)
            self.fields["room_type"].queryset = RoomType.objects.filter(
                agency=request.user.agency, is_active=True
            )
