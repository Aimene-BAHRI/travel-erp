from django.db import transaction
from django.db.models import Q
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.response import Response

from audit.services import record_event
from reference.models import (
    AgencyCurrency,
    City,
    Country,
    Currency,
    PassengerCategory,
    PaymentMethod,
)

from .serializers import (
    AgencyCurrencySerializer,
    CitySerializer,
    CountrySerializer,
    CurrencySerializer,
    PassengerCategorySerializer,
    PaymentMethodSerializer,
)


class SearchableReadOnlyViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]


class CountryViewSet(SearchableReadOnlyViewSet):
    queryset = Country.objects.all()
    serializer_class = CountrySerializer
    search_fields = ["name", "code"]
    ordering_fields = ["name", "code"]


class CityViewSet(SearchableReadOnlyViewSet):
    queryset = City.objects.select_related("country")
    serializer_class = CitySerializer
    search_fields = ["name", "country__name", "country__code"]
    ordering_fields = ["name", "country__name"]

    def get_queryset(self):
        queryset = super().get_queryset()
        country = self.request.query_params.get("country")
        return queryset.filter(country_id=country) if country else queryset


class CurrencyViewSet(SearchableReadOnlyViewSet):
    queryset = Currency.objects.filter(is_active=True)
    serializer_class = CurrencySerializer
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name"]


class AgencyCurrencyViewSet(viewsets.ModelViewSet):
    queryset = AgencyCurrency.objects.select_related("currency")
    serializer_class = AgencyCurrencySerializer
    permission_classes = [DjangoModelPermissions]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().filter(agency=self.request.user.agency)

    def perform_create(self, serializer):
        setting = serializer.save(agency=self.request.user.agency)
        record_event(
            actor=self.request.user,
            action="agency_currency.created",
            target_type="reference.AgencyCurrency",
            target_id=setting.pk,
            request=self.request,
        )

    @action(detail=True, methods=["post"], url_path="make-accounting")
    @transaction.atomic
    def make_accounting(self, request, pk=None):
        setting = get_object_or_404(self.get_queryset().select_for_update(), pk=pk)
        AgencyCurrency.objects.select_for_update().filter(
            agency=request.user.agency, is_accounting=True
        ).exclude(pk=setting.pk).update(is_accounting=False)
        setting.is_enabled = True
        setting.is_accounting = True
        setting.save(update_fields=["is_enabled", "is_accounting", "updated_at"])
        record_event(
            actor=request.user,
            action="agency_currency.accounting_changed",
            target_type="reference.AgencyCurrency",
            target_id=setting.pk,
            metadata={"currency": setting.currency_id},
            request=request,
        )
        return Response(self.get_serializer(setting).data)


class TenantExtensibleReferenceViewSet(viewsets.ModelViewSet):
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    search_fields = ["code", "name"]
    ordering_fields = ["sort_order", "name", "code"]

    def get_queryset(self):
        return super().get_queryset().filter(Q(is_system=True) | Q(agency=self.request.user.agency))

    def perform_create(self, serializer):
        serializer.save(agency=self.request.user.agency, is_system=False)

    def perform_update(self, serializer):
        if self.get_object().is_system:
            raise PermissionDenied("System reference records cannot be modified.")
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.is_system:
            raise PermissionDenied("System reference records cannot be deleted.")
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PassengerCategoryViewSet(TenantExtensibleReferenceViewSet):
    queryset = PassengerCategory.objects.all()
    serializer_class = PassengerCategorySerializer


class PaymentMethodViewSet(TenantExtensibleReferenceViewSet):
    queryset = PaymentMethod.objects.all()
    serializer_class = PaymentMethodSerializer
