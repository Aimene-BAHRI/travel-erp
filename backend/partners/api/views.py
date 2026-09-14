from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import filters, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response

from audit.services import record_event
from partners.models import CommissionPayment, Partner, PartnerAllocation, PartnerCommission
from partners.services import (
    assign_allocation,
    post_commission_payment,
    reverse_commission_payment,
    transition_commission,
)

from .serializers import (
    AllocationSerializer,
    CommissionPaymentSerializer,
    CommissionSerializer,
    CommissionTransitionSerializer,
    PartnerSerializer,
    PaymentInputSerializer,
    ReversalInputSerializer,
    UsageInputSerializer,
)


class TenantViewSet(viewsets.ModelViewSet):
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return super().get_queryset().filter(agency=self.request.user.agency)

    def perform_create(self, serializer):
        self._audit(
            "created",
            serializer.save(agency=self.request.user.agency, created_by=self.request.user),
        )

    def perform_update(self, serializer):
        self._audit("updated", serializer.save())

    def _audit(self, verb, obj, metadata=None):
        record_event(
            actor=self.request.user,
            action=f"partner.{type(obj).__name__.lower()}.{verb}",
            target_type=f"partners.{type(obj).__name__}",
            target_id=obj.pk,
            metadata=metadata,
            request=self.request,
        )

    def _command(self, service, **kwargs):
        try:
            return service(agency=self.request.user.agency, **kwargs)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc


class PartnerViewSet(TenantViewSet):
    queryset = Partner.objects.select_related("branch")
    serializer_class = PartnerSerializer
    search_fields = ["name", "contact_name", "phone", "email"]
    ordering_fields = ["name", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        return (
            queryset.filter(branch=user.branch)
            if user.branch_id and not user.has_perm("partners.view_all_partners")
            else queryset
        )


class AllocationViewSet(TenantViewSet):
    queryset = PartnerAllocation.objects.select_related("partner", "trip").prefetch_related(
        "usages"
    )
    serializer_class = AllocationSerializer
    search_fields = ["partner__name", "trip__name", "trip__code"]
    ordering_fields = ["created_at", "quantity", "trip__departure_date"]

    def get_queryset(self):
        queryset = super().get_queryset()
        trip_id = self.request.query_params.get("trip")
        return queryset.filter(trip_id=trip_id) if trip_id else queryset

    @action(detail=True, methods=["post"])
    def use(self, request, pk=None):
        allocation = self.get_object()
        data = UsageInputSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        usage = self._command(
            assign_allocation,
            allocation_id=allocation.pk,
            actor=request.user,
            **data.validated_data,
        )
        self._audit("usage_added", allocation, {"usage_id": str(usage.pk)})
        allocation.refresh_from_db()
        return Response(self.get_serializer(allocation).data, status=status.HTTP_201_CREATED)


class CommissionViewSet(TenantViewSet):
    queryset = PartnerCommission.objects.select_related(
        "partner", "booking", "currency"
    ).prefetch_related("payments__reverses")
    serializer_class = CommissionSerializer
    search_fields = ["partner__name", "booking__code"]
    ordering_fields = ["created_at", "amount", "status"]

    def get_queryset(self):
        queryset = super().get_queryset()
        trip_id = self.request.query_params.get("trip")
        return queryset.filter(booking__trip_id=trip_id) if trip_id else queryset

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        current = self.get_object()
        data = CommissionTransitionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        item = self._command(
            transition_commission,
            commission_id=current.pk,
            target_status=data.validated_data["status"],
        )
        self._audit("status_changed", item)
        return Response(self.get_serializer(item).data)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        item = self.get_object()
        data = PaymentInputSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        payment = self._command(
            post_commission_payment,
            commission_id=item.pk,
            actor=request.user,
            **data.validated_data,
        )
        self._audit("payment_posted", item, {"payment_id": str(payment.pk)})
        return Response(CommissionPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class CommissionPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = CommissionPayment.objects.select_related(
        "commission__partner", "currency", "payment_method", "reverses"
    )
    serializer_class = CommissionPaymentSerializer
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        queryset = super().get_queryset().filter(agency=self.request.user.agency)
        commission = self.request.query_params.get("commission")
        return queryset.filter(commission_id=commission) if commission else queryset

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        original = self.get_object()
        data = ReversalInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            entry = reverse_commission_payment(
                agency=request.user.agency,
                actor=request.user,
                payment_id=original.pk,
                **data.validated_data,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        record_event(
            actor=request.user,
            action="partner.commission_payment.reversed",
            target_type="partners.CommissionPayment",
            target_id=entry.pk,
            request=request,
        )
        return Response(self.get_serializer(entry).data, status=status.HTTP_201_CREATED)
