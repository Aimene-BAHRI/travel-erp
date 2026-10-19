import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from pricing.services import quantize_money

from .models import (
    CommissionPayment,
    PartnerAllocation,
    PartnerAllocationUsage,
    PartnerCommission,
)


@transaction.atomic
def reserve_ticket_places(*, allocation_id, quantity, agency, actor):
    from trips.models import Trip
    from bookings.readiness import seat_summary

    allocation = PartnerAllocation.objects.select_for_update().select_related("trip").get(
        pk=allocation_id, agency=agency, is_active=True, kind=PartnerAllocation.Kind.TICKETS
    )
    if quantity < 1 or quantity > allocation.remaining_quantity:
        raise ValidationError("Ticket places exceed the partner's remaining allocation.")
    trip = Trip.objects.select_for_update().get(pk=allocation.trip_id)
    summary = seat_summary(trip)
    if summary["remaining"] is not None and quantity > summary["remaining"]:
        raise ValidationError("The trip does not have enough remaining ticket places.")
    allocation.reserved_quantity += quantity
    allocation.full_clean()
    allocation.save(update_fields=["reserved_quantity", "updated_at"])
    return allocation


@transaction.atomic
def reserve_customer_ticket_places(*, trip_id, customer_id, quantity, agency, actor):
    from bookings.readiness import seat_summary
    from customers.models import Customer
    from partners.models import Partner
    from trips.models import Trip

    customer = Customer.objects.select_for_update().get(
        pk=customer_id, agency=agency, is_active=True, kind=Customer.Kind.COMPANY
    )
    trip = Trip.objects.select_for_update().get(pk=trip_id, agency=agency)
    if quantity < 1:
        raise ValidationError("Reserve at least one ticket place.")
    summary = seat_summary(trip)
    if summary["remaining"] is not None and quantity > summary["remaining"]:
        raise ValidationError("The trip does not have enough remaining ticket places.")

    partner, _ = Partner.objects.get_or_create(
        agency=agency,
        name=customer.company_name,
        defaults={
            "branch": customer.branch,
            "kind": Partner.Kind.COMPANY,
            "phone": customer.phone,
            "email": customer.email,
            "address": customer.address,
            "notes": customer.notes,
            "created_by": actor,
        },
    )
    allocation, created = PartnerAllocation.objects.select_for_update().get_or_create(
        agency=agency,
        partner=partner,
        trip=trip,
        kind=PartnerAllocation.Kind.TICKETS,
        defaults={
            "quantity": quantity,
            "reserved_quantity": quantity,
            "notes": "Ticket places reserved from company customer.",
            "created_by": actor,
        },
    )
    if not created:
        allocation.is_active = True
        allocation.quantity += quantity
        allocation.reserved_quantity += quantity
        allocation.full_clean()
        allocation.save(update_fields=["is_active", "quantity", "reserved_quantity", "updated_at"])
    return allocation


@transaction.atomic
def transition_commission(*, commission_id, agency, target_status):
    commission = PartnerCommission.objects.select_for_update().get(pk=commission_id, agency=agency)
    allowed = {
        PartnerCommission.Status.ACCRUED: {
            PartnerCommission.Status.APPROVED,
            PartnerCommission.Status.CANCELLED,
        },
        PartnerCommission.Status.APPROVED: {PartnerCommission.Status.CANCELLED},
        PartnerCommission.Status.CANCELLED: set(),
    }
    if target_status not in allowed[commission.status]:
        raise ValidationError(
            f"Commission cannot transition from {commission.status} to {target_status}."
        )
    if target_status == PartnerCommission.Status.CANCELLED and commission.paid_amount:
        raise ValidationError("A paid commission cannot be cancelled; reverse its payments first.")
    commission.status = target_status
    commission.save(update_fields=["status", "updated_at"])
    return commission


@transaction.atomic
def assign_allocation(*, allocation_id, booking, quantity, agency, actor):
    allocation = PartnerAllocation.objects.select_for_update().get(
        pk=allocation_id, agency=agency, is_active=True
    )
    if booking.agency_id != agency.id or booking.trip_id != allocation.trip_id:
        raise ValidationError("The booking must belong to the allocation trip and agency.")
    if quantity < 1 or quantity > allocation.remaining_quantity:
        raise ValidationError("Allocation usage exceeds the remaining quantity.")
    usage = PartnerAllocationUsage(
        allocation=allocation, booking=booking, quantity=quantity, created_by=actor
    )
    usage.full_clean()
    usage.save()
    return usage


@transaction.atomic
def post_commission_payment(
    *,
    commission_id,
    agency,
    actor,
    amount,
    currency,
    exchange_rate,
    payment_method,
    payment_date,
    reference="",
    notes="",
):
    commission = (
        PartnerCommission.objects.select_for_update()
        .select_related("currency")
        .get(pk=commission_id, agency=agency, status=PartnerCommission.Status.APPROVED)
    )
    amount, exchange_rate = Decimal(amount), Decimal(exchange_rate)
    if amount <= 0 or exchange_rate <= 0:
        raise ValidationError("Amount and exchange rate must be greater than zero.")
    if currency.pk == commission.currency_id and exchange_rate != Decimal("1"):
        raise ValidationError("Same-currency exchange rate must equal 1.")
    converted = quantize_money(amount * exchange_rate, commission.currency)
    if converted > commission.remaining_amount:
        raise ValidationError("Payment exceeds the remaining commission balance.")
    payment = CommissionPayment(
        agency=agency,
        commission=commission,
        number=f"CPY-{payment_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
        kind=CommissionPayment.Kind.PAYMENT,
        amount=amount,
        currency=currency,
        exchange_rate=exchange_rate,
        commission_amount=converted,
        payment_method=payment_method,
        payment_date=payment_date,
        reference=reference,
        notes=notes,
        created_by=actor,
    )
    payment.full_clean()
    payment.save()
    return payment


@transaction.atomic
def reverse_commission_payment(*, payment_id, agency, actor, payment_date, reason):
    original = CommissionPayment.objects.select_for_update().get(
        pk=payment_id, agency=agency, kind=CommissionPayment.Kind.PAYMENT
    )
    if hasattr(original, "reversal"):
        raise ValidationError("This payment has already been reversed.")
    if not reason.strip():
        raise ValidationError("A reversal reason is required.")
    reversal = CommissionPayment(
        agency=agency,
        commission=original.commission,
        number=f"CRV-{payment_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
        kind=CommissionPayment.Kind.REVERSAL,
        amount=original.amount,
        currency=original.currency,
        exchange_rate=original.exchange_rate,
        commission_amount=original.commission_amount,
        payment_method=original.payment_method,
        payment_date=payment_date,
        reference=original.number,
        notes=reason.strip(),
        reverses=original,
        created_by=actor,
    )
    reversal.full_clean()
    reversal.save()
    return reversal
