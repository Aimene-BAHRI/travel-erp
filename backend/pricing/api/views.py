from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response

from audit.services import record_event
from pricing.models import (
    Promotion,
    Quote,
    SeasonalFlightPrice,
    TripCostComponent,
    TripHotelPrice,
    TripOccupancyPackage,
)
from pricing.services import add_price_to_quote, issue_quote, remove_quote_line, transition_quote

from .serializers import (
    AddQuotePriceSerializer,
    PromotionSerializer,
    QuoteSerializer,
    QuoteTransitionSerializer,
    SeasonalFlightPriceSerializer,
    TripCostComponentSerializer,
    TripHotelPriceSerializer,
    TripOccupancyPackageSerializer,
)


class AgencyPricingViewSet(viewsets.ModelViewSet):
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    audit_name = ""

    def get_queryset(self):
        return super().get_queryset().filter(agency=self.request.user.agency)

    def perform_create(self, serializer):
        instance = serializer.save(agency=self.request.user.agency)
        self._audit("created", instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._audit("updated", instance)

    def _audit(self, verb, instance, metadata=None):
        record_event(
            actor=self.request.user,
            action=f"{self.audit_name}.{verb}",
            target_type=f"pricing.{type(instance).__name__}",
            target_id=instance.pk,
            metadata=metadata,
            request=self.request,
        )


class PromotionViewSet(AgencyPricingViewSet):
    queryset = Promotion.objects.select_related("trip")
    serializer_class = PromotionSerializer
    search_fields = ["code", "name", "trip__name"]
    ordering_fields = ["sales_start_date", "sales_end_date", "name", "created_at"]
    audit_name = "promotion"

    def get_queryset(self):
        queryset = super().get_queryset()
        trip_id = self.request.query_params.get("trip")
        return queryset.filter(trip_id=trip_id) if trip_id else queryset


class TripCostComponentViewSet(AgencyPricingViewSet):
    queryset = TripCostComponent.objects.select_related("trip", "source_currency")
    serializer_class = TripCostComponentSerializer
    ordering_fields = ["code", "basis", "applies_to"]
    audit_name = "trip_cost_component"

    def get_queryset(self):
        queryset = super().get_queryset()
        trip_id = self.request.query_params.get("trip")
        return queryset.filter(trip_id=trip_id) if trip_id else queryset


class TripOccupancyPackageViewSet(AgencyPricingViewSet):
    queryset = TripOccupancyPackage.objects.select_related("trip").prefetch_related(
        "trip__cost_components"
    )
    serializer_class = TripOccupancyPackageSerializer
    ordering_fields = ["makkah_occupancy", "name", "code"]
    audit_name = "trip_occupancy_package"

    def get_queryset(self):
        queryset = super().get_queryset()
        trip_id = self.request.query_params.get("trip")
        return queryset.filter(trip_id=trip_id) if trip_id else queryset


class TripHotelPriceViewSet(AgencyPricingViewSet):
    queryset = TripHotelPrice.objects.select_related(
        "trip_hotel__stop__trip",
        "trip_hotel__hotel",
        "room_type",
        "passenger_category",
        "promotion",
        "currency",
    )
    serializer_class = TripHotelPriceSerializer
    search_fields = ["trip_hotel__hotel__name", "room_type__name", "promotion__code"]
    ordering_fields = ["amount", "created_at", "trip_hotel__stop__order"]
    audit_name = "hotel_price"

    def get_queryset(self):
        queryset = super().get_queryset()
        scope = self.request.query_params.get("scope")
        if scope:
            queryset = queryset.filter(scope=scope)
        trip_id = self.request.query_params.get("trip")
        return queryset.filter(trip_hotel__stop__trip_id=trip_id) if trip_id else queryset


class SeasonalFlightPriceViewSet(AgencyPricingViewSet):
    queryset = SeasonalFlightPrice.objects.select_related(
        "trip", "airline", "passenger_category", "currency"
    )
    serializer_class = SeasonalFlightPriceSerializer
    search_fields = ["fare_name", "airline__name", "source_reference", "trip__name"]
    ordering_fields = ["sales_start_date", "sales_end_date", "amount", "created_at"]
    audit_name = "flight_price"

    def get_queryset(self):
        queryset = super().get_queryset()
        trip_id = self.request.query_params.get("trip")
        return queryset.filter(trip_id=trip_id) if trip_id else queryset


class QuoteViewSet(AgencyPricingViewSet):
    queryset = Quote.objects.select_related(
        "agency", "branch", "customer", "trip", "currency", "accounting_currency", "created_by"
    ).prefetch_related("lines", "snapshot")
    serializer_class = QuoteSerializer
    search_fields = ["code", "customer__first_name", "customer__last_name", "trip__name"]
    ordering_fields = ["created_at", "valid_until", "status", "code"]
    audit_name = "quote"

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.branch_id and not user.has_perm("pricing.view_all_quotes"):
            queryset = queryset.filter(branch=user.branch)
        for parameter in ["trip", "customer", "status"]:
            value = self.request.query_params.get(parameter)
            if value:
                queryset = queryset.filter(**{parameter: value})
        return queryset

    def perform_create(self, serializer):
        branch = self.request.user.branch if self.request.user.branch_id else None
        values = {"agency": self.request.user.agency, "created_by": self.request.user}
        if branch:
            values["branch"] = branch
        quote = serializer.save(**values)
        self._audit("created", quote)

    def _run_command(self, command, **kwargs):
        try:
            return command(agency=self.request.user.agency, **kwargs)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    @action(detail=True, methods=["post"], url_path="add-hotel-price")
    def add_hotel_price(self, request, pk=None):
        quote = self.get_object()
        input_serializer = AddQuotePriceSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        price = TripHotelPrice.objects.filter(
            pk=input_serializer.validated_data["price_id"], agency=request.user.agency
        ).first()
        if not price:
            raise serializers.ValidationError({"price_id": "Hotel price not found."})
        line = self._run_command(
            add_price_to_quote,
            quote_id=quote.pk,
            price=price,
            quantity=input_serializer.validated_data["quantity"],
            exchange_rate=input_serializer.validated_data["exchange_rate"],
        )
        self._audit("line_added", quote, {"line_id": str(line.pk), "kind": line.kind})
        return Response(self.get_serializer(quote).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="add-flight-price")
    def add_flight_price(self, request, pk=None):
        quote = self.get_object()
        input_serializer = AddQuotePriceSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        price = SeasonalFlightPrice.objects.filter(
            pk=input_serializer.validated_data["price_id"], agency=request.user.agency
        ).first()
        if not price:
            raise serializers.ValidationError({"price_id": "Flight price not found."})
        line = self._run_command(
            add_price_to_quote,
            quote_id=quote.pk,
            price=price,
            quantity=input_serializer.validated_data["quantity"],
            exchange_rate=input_serializer.validated_data["exchange_rate"],
        )
        self._audit("line_added", quote, {"line_id": str(line.pk), "kind": line.kind})
        return Response(self.get_serializer(quote).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"lines/(?P<line_id>[^/.]+)")
    def remove_line(self, request, pk=None, line_id=None):
        quote = self.get_object()
        self._run_command(remove_quote_line, quote_id=quote.pk, line_id=line_id)
        self._audit("line_removed", quote, {"line_id": str(line_id)})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def issue(self, request, pk=None):
        quote = self.get_object()
        quote = self._run_command(issue_quote, quote_id=quote.pk)
        self._audit("issued", quote, {"snapshot_sha256": quote.snapshot.sha256})
        return Response(self.get_serializer(quote).data)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        quote = self.get_object()
        input_serializer = QuoteTransitionSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        previous = quote.status
        quote = self._run_command(
            transition_quote,
            quote_id=quote.pk,
            target_status=input_serializer.validated_data["status"],
        )
        self._audit("status_changed", quote, {"from": previous, "to": quote.status})
        return Response(self.get_serializer(quote).data)
