from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from audit.services import record_event
from finance.models import AirlineInstallment, AirlinePricing
from finance.services import post_cash_entry
from pricing.models import TripCostComponent
from reference.models import AgencyCurrency
from trips.models import Trip

from .serializers import AgencyCashEntryInputSerializer

CATEGORIES = [
    "ADULT",
    "CHD",
    "INF",
    "FREE",
    "DISCOUNT_50",
    "DISCOUNT_60",
    "DISCOUNT_100",
    "REV",
    "SHENTOS",
    "REVALIDATION",
    "LESS_10",
    "MORE_10",
    "INF_SEAT",
]

SEAT_CATEGORIES = {"ADULT", "CHD", "INF_SEAT", "FREE", "DISCOUNT_50", "DISCOUNT_60", "DISCOUNT_100"}


def dzd_currency_for(agency):
    """Airline pricing is denominated in DZD and needs an enabled DZD setting."""
    currency = (
        AgencyCurrency.objects.filter(agency=agency, currency_id="DZD", is_enabled=True)
        .values_list("currency_id", flat=True)
        .first()
    )
    if not currency:
        raise serializers.ValidationError(
            {"currency": "Enable DZD in the agency currency settings before using airline finance."}
        )
    return currency


class AirlinePermission(BasePermission):
    def has_permission(self, request, view):
        permission = "view_trip" if request.method in ("GET", "HEAD", "OPTIONS") else "change_trip"
        return request.user.has_perm(f"trips.{permission}") and (
            not str(view.action).startswith("installment")
            or request.method == "GET"
            or request.user.has_perm("finance.add_agencycashentry")
        )


class PricingRowSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=CATEGORIES)
    seats = serializers.IntegerField(min_value=0, max_value=65535)
    price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"), allow_null=True)

    def validate(self, attrs):
        if attrs["price"] is None and (attrs["category"] not in {"CHD", "INF", "INF_SEAT"} or attrs["seats"]):
            raise serializers.ValidationError({"price": "Enter a fare for this category."})
        return attrs


class PricingInputSerializer(serializers.Serializer):
    rows = PricingRowSerializer(many=True)
    visa_price = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"))

    def validate_rows(self, rows):
        if sorted(row["category"] for row in rows) != sorted(CATEGORIES):
            raise serializers.ValidationError("Provide each pricing category exactly once.")
        return rows


class AirlineInstallmentSerializer(serializers.ModelSerializer):
    date = serializers.SerializerMethodField()
    reference = serializers.SerializerMethodField()
    amount = serializers.SerializerMethodField()
    notes = serializers.SerializerMethodField()
    payment_method = serializers.SerializerMethodField()
    is_paid = serializers.SerializerMethodField()

    def get_date(self, obj):
        return obj.cash_entry.entry_date if obj.cash_entry_id else None

    def get_reference(self, obj):
        return obj.cash_entry.reference if obj.cash_entry_id else obj.scheduled_reference

    def get_amount(self, obj):
        return str(obj.cash_entry.amount if obj.cash_entry_id else obj.scheduled_amount)

    def get_notes(self, obj):
        return obj.cash_entry.notes if obj.cash_entry_id else obj.scheduled_notes

    def get_payment_method(self, obj):
        return str(obj.cash_entry.payment_method_id) if obj.cash_entry_id else None

    def get_is_paid(self, obj):
        return obj.cash_entry_id is not None

    class Meta:
        model = AirlineInstallment
        fields = [
            "id",
            "date",
            "due_date",
            "is_paid",
            "reference",
            "amount",
            "notes",
            "payment_method",
            "attachment",
        ]


class ScheduleSerializer(serializers.Serializer):
    due_date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    reference = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class AirlineFinanceViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, AirlinePermission]
    queryset = Trip.objects.all()

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            exc = serializers.ValidationError(exc.messages)
        return super().handle_exception(exc)

    def get_queryset(self):
        return super().get_queryset().filter(agency=self.request.user.agency)

    def payload(self, trip):
        pricing = AirlinePricing.objects.filter(trip=trip).first()
        rows = (
            pricing.effective_rows
            if pricing
            else AirlinePricing(trip=trip, rows=[
                {"category": category, "seats": 0, "price": None if category in {"ADULT", "CHD", "INF", "INF_SEAT"} else "0.00"}
                for category in CATEGORIES
            ]).effective_rows
        )
        installments = (
            pricing.installments.filter(voided_at__isnull=True)
            .select_related("cash_entry")
            .order_by("due_date", "cash_entry__entry_date", "id")
            if pricing
            else []
        )
        paid = sum(
            (item.cash_entry.amount for item in installments if item.cash_entry_id), Decimal("0")
        )
        scheduled = sum(
            (item.scheduled_amount for item in installments if not item.cash_entry_id), Decimal("0")
        )
        pricing_error = None
        try:
            total = pricing.total if pricing else Decimal("0")
        except DjangoValidationError as exc:
            total = None
            pricing_error = " ".join(exc.messages)
        return {
            "rows": rows,
            "quantities_from_bookings": AirlinePricing(trip=trip).quantities_from_bookings,
            "unbooked_seats": (pricing or AirlinePricing(trip=trip)).unbooked_seats,
            "confirmed_counts": dict((pricing or AirlinePricing(trip=trip)).passenger_counts),
            "visa_price": str(pricing.visa_price) if pricing else "0.00",
            "active": pricing is not None,
            "pricing_error": pricing_error,
            "total": str(total) if total is not None else None,
            "paid": str(paid),
            "remaining": str(total - paid) if total is not None else None,
            "scheduled": str(scheduled),
            "unscheduled": str(max(Decimal("0"), total - paid - scheduled)) if total is not None else None,
            "progress": str(paid / total * 100 if total else 0),
            "installments": AirlineInstallmentSerializer(
                installments, many=True, context={"request": self.request}
            ).data,
        }

    def retrieve(self, request, pk=None):
        return Response(self.payload(self.get_object()))

    @transaction.atomic
    def update(self, request, pk=None):
        trip = get_object_or_404(self.get_queryset().select_for_update(), pk=pk)
        dzd_currency_for(trip.agency)
        data = PricingInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        rows = data.validated_data["rows"]
        submitted_seats = sum(row["seats"] for row in rows if row["category"] in SEAT_CATEGORIES)
        if trip.max_travelers is not None and submitted_seats > trip.max_travelers:
            raise serializers.ValidationError({"rows": "Seats allocated exceed trip capacity."})
        existing = AirlinePricing(trip=trip, rows=rows)
        rows = existing.effective_rows
        seats = sum(row["seats"] for row in rows if row["category"] in SEAT_CATEGORIES)
        if trip.max_travelers is not None and seats > trip.max_travelers:
            raise serializers.ValidationError({"rows": "Seats allocated exceed trip capacity."})
        for row in rows:
            if row["seats"] and row["price"] is None:
                raise serializers.ValidationError({"rows": f"Enter the airline fare for {row['category']}."})
            if row["price"] is not None:
                row["price"] = str(row["price"])
        AirlinePricing.objects.update_or_create(
            trip=trip, defaults={**data.validated_data, "rows": rows}
        )
        # Visa is shared by all age categories in component-based package calculations.
        TripCostComponent.objects.update_or_create(
            trip=trip,
            code="airline-visa",
            applies_to="ALL",
            defaults={
                "agency": trip.agency,
                "label": "Visa",
                "source_amount": data.validated_data["visa_price"],
                "source_currency_id": "DZD",
                "exchange_rate": 1,
                "quantity": 1,
                "basis": "PER_TRAVELER",
                "is_active": True,
            },
        )
        record_event(
            actor=request.user,
            action="airline_pricing.saved",
            target_type="trips.Trip",
            target_id=trip.pk,
            request=request,
        )
        return Response(self.payload(trip))

    @action(detail=True, methods=["post"])
    @transaction.atomic
    def installments(self, request, pk=None):
        trip = get_object_or_404(self.get_queryset().select_for_update(), pk=pk)
        pricing = get_object_or_404(AirlinePricing, trip=trip)
        currency = dzd_currency_for(trip.agency)
        attachment = self._attachment(request)
        if attachment and (
            attachment.size > 10 * 1024 * 1024
            or attachment.content_type not in ["application/pdf", "image/jpeg", "image/png"]
        ):
            raise serializers.ValidationError({"attachment": "Use a PDF, JPEG or PNG up to 10 MB."})
        data = AgencyCashEntryInputSerializer(
            data={
                "branch": str(trip.branch_id),
                "trip": str(trip.pk),
                "direction": "OUT",
                "category": "OTHER_EXPENSE",
                "description": f"Airline installment: {trip.code}",
                "currency": currency,
                **{
                    key: request.data.get(key, "")
                    for key in ["amount", "payment_method", "entry_date", "reference", "notes"]
                },
            },
            context={"request": request},
        )
        data.is_valid(raise_exception=True)
        paid = sum(
            (
                item.cash_entry.amount
                for item in pricing.installments.filter(
                    voided_at__isnull=True, cash_entry__isnull=False
                ).select_related("cash_entry")
            ),
            Decimal("0"),
        )
        if data.validated_data["amount"] > pricing.total - paid:
            raise serializers.ValidationError(
                {"amount": "Amount exceeds the remaining flight balance."}
            )
        entry = post_cash_entry(agency=trip.agency, actor=request.user, **data.validated_data)
        installment = AirlineInstallment.objects.create(
            pricing=pricing,
            cash_entry=entry,
            attachment=attachment or "",
            due_date=serializers.DateField(allow_null=True).run_validation(
                request.data.get("due_date") or None
            ),
        )
        record_event(
            actor=request.user,
            action="airline_installment.created",
            target_type="finance.AirlineInstallment",
            target_id=installment.pk,
            request=request,
        )
        return Response(self.payload(trip), status=201)

    def _void_installment(self, *, installment, actor):
        entry = installment.cash_entry
        reversal = None
        if entry:
            reversal = post_cash_entry(
                agency=entry.agency,
                actor=actor,
                branch=entry.branch,
                trip=entry.trip,
                direction="IN",
                category="OTHER_INCOME",
                description=f"Void airline installment: {entry.number}",
                amount=entry.amount,
                currency=entry.currency,
                payment_method=entry.payment_method,
                entry_date=timezone.localdate(),
                reference=f"VOID-{entry.number}",
                notes="Airline installment voided.",
            )
        installment.voided_at = timezone.now()
        installment.voided_by = actor
        installment.reversal_cash_entry = reversal
        installment.save(update_fields=["voided_at", "voided_by", "reversal_cash_entry"])

    @action(
        detail=True,
        methods=["patch", "delete"],
        url_path=r"installments/(?P<installment_id>[^/.]+)",
    )
    @transaction.atomic
    def installment(self, request, pk=None, installment_id=None):
        trip = get_object_or_404(self.get_queryset().select_for_update(), pk=pk)
        installment = get_object_or_404(
            AirlineInstallment.objects.select_related("cash_entry", "pricing").select_for_update(
                of=("self",)
            ),
            pk=installment_id,
            pricing__trip=trip,
            voided_at__isnull=True,
        )
        if request.method == "DELETE":
            self._void_installment(installment=installment, actor=request.user)
            record_event(
                actor=request.user,
                action="airline_installment.voided",
                target_type="finance.AirlineInstallment",
                target_id=installment.pk,
                request=request,
            )
            return Response(self.payload(trip), status=200)

        if not installment.cash_entry_id:
            data = ScheduleSerializer(data=request.data)
            data.is_valid(raise_exception=True)
            self._check_schedule_balance(
                installment.pricing, data.validated_data["amount"], exclude=installment.pk
            )
            installment.due_date = data.validated_data["due_date"]
            installment.scheduled_amount = data.validated_data["amount"]
            installment.scheduled_reference = data.validated_data["reference"]
            installment.scheduled_notes = data.validated_data["notes"]
            if request.FILES.get("attachment"):
                installment.attachment = self._attachment(request)
            installment.save()
            record_event(
                actor=request.user,
                action="airline_installment.updated",
                target_type="finance.AirlineInstallment",
                target_id=installment.pk,
                request=request,
            )
            return Response(self.payload(trip))

        old_attachment = installment.attachment
        self._void_installment(installment=installment, actor=request.user)
        attachment = self._attachment(request)
        currency = dzd_currency_for(trip.agency)
        data = AgencyCashEntryInputSerializer(
            data={
                "branch": str(trip.branch_id),
                "trip": str(trip.pk),
                "direction": "OUT",
                "category": "OTHER_EXPENSE",
                "description": f"Airline installment: {trip.code}",
                "currency": currency,
                **{
                    key: request.data.get(key, "")
                    for key in ["amount", "payment_method", "entry_date", "reference", "notes"]
                },
            },
            context={"request": request},
        )
        data.is_valid(raise_exception=True)
        paid = sum(
            (
                item.cash_entry.amount
                for item in trip.airline_pricing.installments.filter(
                    voided_at__isnull=True, cash_entry__isnull=False
                )
            ),
            Decimal("0"),
        )
        # Falling booking quantities can lower the current flight total below
        # historical payments. Existing payments must remain correctable.
        if data.validated_data["amount"] > max(
            installment.cash_entry.amount, trip.airline_pricing.total - paid
        ):
            raise serializers.ValidationError(
                {"amount": "Amount exceeds the remaining flight balance."}
            )
        entry = post_cash_entry(agency=trip.agency, actor=request.user, **data.validated_data)
        replacement = AirlineInstallment.objects.create(
            pricing=trip.airline_pricing,
            cash_entry=entry,
            attachment=attachment if attachment else old_attachment,
            due_date=serializers.DateField(allow_null=True).run_validation(
                request.data.get("due_date", installment.due_date) or None
            ),
        )
        record_event(
            actor=request.user,
            action="airline_installment.updated",
            target_type="finance.AirlineInstallment",
            target_id=replacement.pk,
            request=request,
        )
        return Response(self.payload(trip), status=200)

    def _attachment(self, request):
        attachment = request.FILES.get("attachment")
        if attachment and (
            attachment.size > 10 * 1024 * 1024
            or attachment.content_type not in ["application/pdf", "image/jpeg", "image/png"]
        ):
            raise serializers.ValidationError({"attachment": "Use a PDF, JPEG or PNG up to 10 MB."})
        return attachment

    def _check_schedule_balance(self, pricing, amount, exclude=None):
        allocated = sum(
            (
                item.cash_entry.amount if item.cash_entry_id else item.scheduled_amount
                for item in pricing.installments.filter(voided_at__isnull=True)
                .exclude(pk=exclude)
                .select_related("cash_entry")
            ),
            Decimal("0"),
        )
        original_amount = (
            pricing.installments.get(pk=exclude).scheduled_amount if exclude else Decimal("0")
        )
        if amount > max(original_amount, pricing.total - allocated):
            raise serializers.ValidationError(
                {"amount": "Amount exceeds the unscheduled flight balance."}
            )

    @action(detail=True, methods=["post"], url_path="schedule-installment")
    @transaction.atomic
    def installment_schedule(self, request, pk=None):
        trip = get_object_or_404(self.get_queryset().select_for_update(), pk=pk)
        pricing = get_object_or_404(AirlinePricing, trip=trip)
        dzd_currency_for(trip.agency)
        data = ScheduleSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        self._check_schedule_balance(pricing, data.validated_data["amount"])
        item = AirlineInstallment.objects.create(
            pricing=pricing,
            due_date=data.validated_data["due_date"],
            scheduled_amount=data.validated_data["amount"],
            scheduled_reference=data.validated_data["reference"],
            scheduled_notes=data.validated_data["notes"],
            attachment=self._attachment(request) or "",
        )
        record_event(
            actor=request.user,
            action="airline_installment.scheduled",
            target_type="finance.AirlineInstallment",
            target_id=item.pk,
            request=request,
        )
        return Response(self.payload(trip), status=201)

    @action(detail=True, methods=["post"], url_path=r"installments/(?P<installment_id>[^/.]+)/pay")
    @transaction.atomic
    def installment_pay(self, request, pk=None, installment_id=None):
        trip = get_object_or_404(self.get_queryset().select_for_update(), pk=pk)
        item = get_object_or_404(
            AirlineInstallment.objects.select_for_update(),
            pk=installment_id,
            pricing__trip=trip,
            voided_at__isnull=True,
        )
        if item.cash_entry_id:
            raise serializers.ValidationError("This installment is already paid.")
        data = AgencyCashEntryInputSerializer(
            data={
                "branch": str(trip.branch_id),
                "trip": str(trip.pk),
                "direction": "OUT",
                "category": "OTHER_EXPENSE",
                "description": f"Airline installment: {trip.code}",
                "currency": dzd_currency_for(trip.agency),
                "amount": str(item.scheduled_amount),
                "payment_method": request.data.get("payment_method"),
                "entry_date": request.data.get("entry_date"),
                "reference": item.scheduled_reference,
                "notes": item.scheduled_notes,
            },
            context={"request": request},
        )
        data.is_valid(raise_exception=True)
        paid = sum(
            (
                x.cash_entry.amount
                for x in item.pricing.installments.filter(
                    voided_at__isnull=True, cash_entry__isnull=False
                ).select_related("cash_entry")
            ),
            Decimal("0"),
        )
        if item.scheduled_amount > item.pricing.total - paid:
            raise serializers.ValidationError(
                {"amount": "Amount exceeds the remaining flight balance."}
            )
        attachment = self._attachment(request)
        item.cash_entry = post_cash_entry(
            agency=trip.agency, actor=request.user, **data.validated_data
        )
        if attachment:
            item.attachment = attachment
        item.save(update_fields=["cash_entry", "attachment"])
        record_event(
            actor=request.user,
            action="airline_installment.paid",
            target_type="finance.AirlineInstallment",
            target_id=item.pk,
            request=request,
        )
        return Response(self.payload(trip))
