from django.db.models import Count
from rest_framework import filters, viewsets
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated

from audit.services import record_event
from catalog.models import Airline, Hotel, Room, RoomType, Supplier

from .serializers import (
    AirlineSerializer,
    HotelSerializer,
    RoomSerializer,
    RoomTypeSerializer,
    SupplierSerializer,
)


class AuditedTenantCatalogViewSet(viewsets.ModelViewSet):
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    http_method_names = ["get", "post", "patch", "head", "options"]
    audit_target = ""

    def get_queryset(self):
        return super().get_queryset().filter(agency=self.request.user.agency)

    def perform_create(self, serializer):
        instance = serializer.save(agency=self.request.user.agency)
        self._audit("created", instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._audit("updated", instance)

    def _audit(self, verb, instance):
        record_event(
            actor=self.request.user,
            action=f"{self.audit_target.lower()}.{verb}",
            target_type=f"catalog.{self.audit_target}",
            target_id=instance.pk,
            request=self.request,
        )


class SupplierViewSet(AuditedTenantCatalogViewSet):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    search_fields = ["name", "legal_name", "contact_name", "phone", "email"]
    ordering_fields = ["name", "created_at", "updated_at"]
    audit_target = "Supplier"


class AirlineViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Airline.objects.filter(is_active=True).select_related("country")
    serializer_class = AirlineSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name", "iata_code", "icao_code"]
    ordering_fields = ["name", "iata_code"]


class HotelViewSet(AuditedTenantCatalogViewSet):
    queryset = (
        Hotel.objects.select_related("city__country")
        .annotate(room_count=Count("rooms"))
        .order_by("name", "id")
    )
    serializer_class = HotelSerializer
    search_fields = ["name", "city__name", "city__country__name", "address"]
    ordering_fields = ["name", "star_rating", "created_at", "city__name"]
    audit_target = "Hotel"

    def get_queryset(self):
        queryset = super().get_queryset()
        city = self.request.query_params.get("city")
        return queryset.filter(city_id=city) if city else queryset


class RoomTypeViewSet(AuditedTenantCatalogViewSet):
    queryset = RoomType.objects.all()
    serializer_class = RoomTypeSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["sort_order", "name", "default_standard_beds"]
    audit_target = "RoomType"


class RoomViewSet(AuditedTenantCatalogViewSet):
    queryset = Room.objects.select_related("hotel", "room_type")
    serializer_class = RoomSerializer
    search_fields = ["number", "hotel__name", "room_type__name", "floor"]
    ordering_fields = ["hotel__name", "number", "floor", "standard_beds"]
    audit_target = "Room"

    def get_queryset(self):
        queryset = super().get_queryset()
        hotel = self.request.query_params.get("hotel")
        room_type = self.request.query_params.get("room_type")
        if hotel:
            queryset = queryset.filter(hotel_id=hotel)
        if room_type:
            queryset = queryset.filter(room_type_id=room_type)
        return queryset
