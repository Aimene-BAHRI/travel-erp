from django.core.exceptions import ValidationError as DjangoValidationError
from num2words import num2words
from rest_framework import filters, mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response

from audit.services import record_event
from bookings.models import Booking
from finance.models import AgencyCashEntry, ExchangeRate, ExpensePayment, FinancialTransaction, TripExpense
from finance.services import (
    booking_financial_summary,
    cash_flow_summary,
    post_cash_entry,
    post_expense_payment,
    post_transaction,
    reverse_expense_payment,
    reverse_transaction,
)

from .serializers import (
    ExchangeRateSerializer,
    ExpensePaymentInputSerializer,
    ExpensePaymentSerializer,
    FinancialSummarySerializer,
    FinancialTransactionSerializer,
    PostTransactionSerializer,
    ReversalSerializer,
    TripExpenseSerializer,
    AgencyCashEntryInputSerializer,
    AgencyCashEntrySerializer,
)

ARABIC_CURRENCY_NAMES = {
    "DZD": "دينار جزائري",
    "EUR": "يورو",
    "SAR": "ريال سعودي",
    "USD": "دولار أمريكي",
}


def amount_in_words_ar(amount, currency_code):
    currency_name = ARABIC_CURRENCY_NAMES.get(currency_code, currency_code)
    return f"{num2words(amount, lang='ar')} {currency_name}"


class AgencyCashEntryViewSet(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    queryset = AgencyCashEntry.objects.select_related("branch", "trip", "currency", "payment_method", "created_by")
    serializer_class = AgencyCashEntrySerializer
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        queryset = super().get_queryset().filter(agency=self.request.user.agency)
        trip_id = self.request.query_params.get("trip")
        return queryset.filter(trip_id=trip_id) if trip_id else queryset

    @action(detail=False, methods=["post"])
    def post(self, request):
        data = AgencyCashEntryInputSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        entry = post_cash_entry(agency=request.user.agency, actor=request.user, **data.validated_data)
        return Response(self.get_serializer(entry).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def report(self, request):
        return Response(cash_flow_summary(agency=request.user.agency, trip_id=request.query_params.get("trip")))


class ExchangeRateViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = ExchangeRate.objects.select_related(
        "source_currency", "target_currency", "created_by"
    )
    serializer_class = ExchangeRateSerializer
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["effective_date", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(agency=self.request.user.agency)
        source = self.request.query_params.get("source_currency")
        target = self.request.query_params.get("target_currency")
        if source:
            queryset = queryset.filter(source_currency_id=source)
        if target:
            queryset = queryset.filter(target_currency_id=target)
        return queryset

    def perform_create(self, serializer):
        rate = serializer.save(agency=self.request.user.agency, created_by=self.request.user)
        record_event(
            actor=self.request.user,
            action="exchange_rate.created",
            target_type="finance.ExchangeRate",
            target_id=rate.pk,
            request=self.request,
        )


class FinancialTransactionViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = FinancialTransaction.objects.select_related(
        "booking__customer",
        "branch",
        "currency",
        "booking_currency",
        "accounting_currency",
        "payment_method",
        "reverses",
        "created_by",
    ).prefetch_related("traveler_allocations__booking_traveler__traveler")
    serializer_class = FinancialTransactionSerializer
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["number", "reference", "booking__code"]
    ordering_fields = ["transaction_date", "created_at", "amount", "kind"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(agency=self.request.user.agency)
        user = self.request.user
        if user.branch_id and not user.has_perm("finance.view_all_financial_transactions"):
            queryset = queryset.filter(branch=user.branch)
        booking_id = self.request.query_params.get("booking")
        trip_id = self.request.query_params.get("trip")
        if booking_id:
            queryset = queryset.filter(booking_id=booking_id)
        if trip_id:
            queryset = queryset.filter(booking__trip_id=trip_id)
        return queryset

    def _command(self, service, **kwargs):
        try:
            return service(agency=self.request.user.agency, **kwargs)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc

    def _post(self, request, kind):
        input_serializer = PostTransactionSerializer(
            data=request.data, context={"request": request}
        )
        input_serializer.is_valid(raise_exception=True)
        entry = self._command(
            post_transaction,
            actor=request.user,
            booking_id=input_serializer.validated_data.pop("booking").pk,
            kind=kind,
            **input_serializer.validated_data,
        )
        self._audit(f"financial.{kind.lower()}_posted", entry)
        return Response(self.get_serializer(entry).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def payments(self, request):
        return self._post(request, FinancialTransaction.Kind.PAYMENT)

    @action(detail=False, methods=["post"])
    def refunds(self, request):
        return self._post(request, FinancialTransaction.Kind.REFUND)

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        original = self.get_object()
        input_serializer = ReversalSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        entry = self._command(
            reverse_transaction,
            actor=request.user,
            transaction_id=original.pk,
            **input_serializer.validated_data,
        )
        self._audit(
            "financial.transaction_reversed",
            entry,
            {"original_transaction_id": str(original.pk)},
        )
        return Response(self.get_serializer(entry).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="booking-summary")
    def booking_summary(self, request):
        booking_id = request.query_params.get("booking")
        if not booking_id:
            raise serializers.ValidationError({"booking": "This query parameter is required."})
        bookings = Booking.objects.filter(agency=request.user.agency)
        if request.user.branch_id and not request.user.has_perm("bookings.view_all_bookings"):
            bookings = bookings.filter(branch=request.user.branch)
        booking = bookings.get(pk=booking_id)
        return Response(FinancialSummarySerializer(booking_financial_summary(booking)).data)

    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        entry = self.get_object()
        if entry.kind != FinancialTransaction.Kind.PAYMENT:
            raise serializers.ValidationError("Receipts are only available for payments.")
        booking = entry.booking
        room_groups = booking.room_groups.select_related(
            "trip_hotel__hotel", "trip_hotel__stop__city", "room_type"
        )
        accommodations = booking.accommodations.select_related(
            "trip_hotel__hotel", "trip_hotel__stop__city", "room_type"
        )
        lodging_rows = list(room_groups) or list(accommodations)
        return Response(
            {
                "receipt_number": entry.number,
                "agency_name": entry.agency.name,
                "agency_logo": (
                    request.build_absolute_uri(entry.agency.logo.url) if entry.agency.logo else None
                ),
                "branch_name": entry.branch.name,
                "booking_code": booking.code,
                "customer_name": booking.customer.display_name,
                "customer_phone": booking.customer.phone,
                "trip_name": booking.trip.name,
                "amount_in_words_ar": amount_in_words_ar(entry.amount, entry.currency_id),
                "hotels": list(
                    dict.fromkeys(
                        f"{row.trip_hotel.stop.city.name}: {row.trip_hotel.hotel.name}"
                        for row in lodging_rows
                    )
                ),
                "room_types": list(dict.fromkeys(row.room_type.name for row in lodging_rows)),
                "financial_summary": FinancialSummarySerializer(
                    booking_financial_summary(booking)
                ).data,
                "transaction": self.get_serializer(entry).data,
            }
        )

    def _audit(self, action_name, entry, metadata=None):
        record_event(
            actor=self.request.user,
            action=action_name,
            target_type="finance.FinancialTransaction",
            target_id=entry.pk,
            metadata=metadata,
            request=self.request,
        )


class TripExpenseViewSet(viewsets.ModelViewSet):
    queryset = TripExpense.objects.select_related(
        "trip", "branch", "supplier", "currency"
    ).prefetch_related("payments__reverses")
    serializer_class = TripExpenseSerializer
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["description", "supplier__name", "trip__name", "trip__code"]
    ordering_fields = ["due_date", "amount", "created_at", "status", "category"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = super().get_queryset().filter(agency=self.request.user.agency)
        trip_id = self.request.query_params.get("trip")
        return queryset.filter(trip_id=trip_id) if trip_id else queryset

    def perform_create(self, serializer):
        trip = serializer.validated_data["trip"]
        expense = serializer.save(
            agency=self.request.user.agency, branch=trip.branch, created_by=self.request.user
        )
        expense.full_clean()
        expense.save()
        self._audit("finance.trip_expense.created", expense)

    def perform_update(self, serializer):
        expense = serializer.save()
        expense.full_clean()
        expense.save()
        self._audit("finance.trip_expense.updated", expense)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        expense = self.get_object()
        data = ExpensePaymentInputSerializer(data=request.data, context={"request": request})
        data.is_valid(raise_exception=True)
        try:
            payment = post_expense_payment(
                agency=request.user.agency,
                actor=request.user,
                expense_id=expense.pk,
                **data.validated_data,
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        self._audit("finance.expense_payment.posted", payment)
        return Response(ExpensePaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

    def _audit(self, action_name, obj):
        record_event(
            actor=self.request.user,
            action=action_name,
            target_type=f"finance.{type(obj).__name__}",
            target_id=obj.pk,
            request=self.request,
        )


class ExpensePaymentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ExpensePayment.objects.select_related(
        "expense__trip", "currency", "payment_method", "reverses"
    )
    serializer_class = ExpensePaymentSerializer
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        queryset = super().get_queryset().filter(agency=self.request.user.agency)
        expense_id = self.request.query_params.get("expense")
        trip_id = self.request.query_params.get("trip")
        if expense_id:
            queryset = queryset.filter(expense_id=expense_id)
        if trip_id:
            queryset = queryset.filter(expense__trip_id=trip_id)
        return queryset

    @action(detail=True, methods=["post"])
    def reverse(self, request, pk=None):
        original = self.get_object()
        data = ReversalSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        try:
            payment = reverse_expense_payment(
                agency=request.user.agency,
                actor=request.user,
                payment_id=original.pk,
                payment_date=data.validated_data["transaction_date"],
                reason=data.validated_data["reason"],
            )
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        record_event(
            actor=request.user,
            action="finance.expense_payment.reversed",
            target_type="finance.ExpensePayment",
            target_id=payment.pk,
            request=request,
        )
        return Response(self.get_serializer(payment).data, status=status.HTTP_201_CREATED)
