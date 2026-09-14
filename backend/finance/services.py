import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from bookings.models import Booking
from pricing.services import quantize_money

from .models import AgencyCashEntry, ExpensePayment, FinancialTransaction, PaymentAllocation, TripExpense


def cash_flow_summary(*, agency, trip_id=None):
    transactions = FinancialTransaction.objects.filter(agency=agency)
    expense_payments = ExpensePayment.objects.filter(agency=agency)
    cash_entries = AgencyCashEntry.objects.filter(agency=agency)
    if trip_id:
        transactions = transactions.filter(booking__trip_id=trip_id)
        expense_payments = expense_payments.filter(expense__trip_id=trip_id)
        cash_entries = cash_entries.filter(trip_id=trip_id)

    totals = {}
    rows = []
    for entry in transactions.select_related("currency", "booking"):
        amount = entry.amount * entry.direction
        rows.append({"number": entry.number, "date": entry.transaction_date, "kind": entry.kind,
                     "description": f"Booking {entry.booking.code}", "currency": entry.currency_id,
                     "amount": amount})
    for entry in expense_payments.select_related("currency", "expense"):
        amount = entry.amount if entry.kind == ExpensePayment.Kind.PAYMENT else -entry.amount
        rows.append({"number": entry.number, "date": entry.payment_date, "kind": entry.kind,
                     "description": entry.expense.description, "currency": entry.currency_id,
                     "amount": -amount})
    for entry in cash_entries.select_related("currency", "trip"):
        rows.append({"number": entry.number, "date": entry.entry_date, "kind": entry.direction,
                     "description": entry.description, "recipient_name": entry.recipient_name,
                     "currency": entry.currency_id, "amount": entry.signed_amount,
                     "source_amount": entry.source_amount, "source_currency": entry.source_currency_id,
                     "exchange_rate": entry.exchange_rate})
    for row in rows:
        summary = totals.setdefault(row["currency"], {"inflow": Decimal("0"), "outflow": Decimal("0"), "net": Decimal("0")})
        if row["amount"] >= 0:
            summary["inflow"] += row["amount"]
        else:
            summary["outflow"] += -row["amount"]
        summary["net"] += row["amount"]
    rows.sort(key=lambda row: (row["date"], row["number"]), reverse=True)
    return {"trip": trip_id, "totals_by_currency": totals, "entries": rows}


@transaction.atomic
def post_cash_entry(*, agency, actor, branch, trip=None, direction, category, description,
                    amount, currency, payment_method, entry_date, reference="", notes="",
                    recipient_name="", source_amount=None, source_currency=None, exchange_rate=None):
    _validate_method(payment_method, agency)
    amount = Decimal(amount)
    if amount <= 0:
        raise ValidationError("Amount must be greater than zero.")
    if trip and (trip.agency_id != agency.id or trip.branch_id != branch.id):
        raise ValidationError("Trip and branch must belong to the agency and match each other.")
    if any(value is not None for value in (source_amount, source_currency, exchange_rate)) and not all(
        value is not None for value in (source_amount, source_currency, exchange_rate)
    ):
        raise ValidationError("Source amount, source currency, and exchange rate must be provided together.")
    if source_currency and source_currency.pk == currency.pk:
        raise ValidationError("Source and target currencies must differ for a conversion.")
    entry = AgencyCashEntry(
        agency=agency, branch=branch, trip=trip,
        number=f"CASH-{entry_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
        direction=direction, category=category, description=description,
        recipient_name=recipient_name, amount=amount, currency=currency,
        source_amount=source_amount, source_currency=source_currency, exchange_rate=exchange_rate,
        payment_method=payment_method,
        entry_date=entry_date, reference=reference, notes=notes, created_by=actor,
    )
    entry.full_clean()
    entry.save()
    return entry


def booking_financial_summary(booking):
    entries = list(
        booking.financial_transactions.select_related("reverses").order_by(
            "transaction_date", "created_at"
        )
    )
    booking_paid = sum((item.signed_booking_amount for item in entries), Decimal("0"))
    accounting_paid = sum((item.signed_accounting_amount for item in entries), Decimal("0"))
    traveler_balances = []
    for traveler in booking.travelers.select_related("traveler").prefetch_related(
        "charges__discounts", "payment_allocations__transaction__reverses"
    ):
        total = sum((charge.final_amount for charge in traveler.charges.all()), Decimal("0"))
        traveler_paid = sum(
            (
                allocation.amount * allocation.transaction.direction
                for allocation in traveler.payment_allocations.all()
            ),
            Decimal("0"),
        )
        traveler_balances.append(
            {
                "booking_traveler": str(traveler.pk),
                "traveler_name": traveler.traveler.display_name,
                "total_amount": total,
                "paid_amount": traveler_paid,
                "remaining_amount": total - traveler_paid,
            }
        )
    return {
        "booking_total": booking.total_amount,
        "paid_amount": booking_paid,
        "remaining_amount": booking.total_amount - booking_paid,
        "currency": booking.currency_id,
        "accounting_total": booking.accounting_total_amount,
        "accounting_paid_amount": accounting_paid,
        "accounting_remaining_amount": booking.accounting_total_amount - accounting_paid,
        "accounting_currency": booking.accounting_currency_id,
        "traveler_balances": traveler_balances,
    }


def _validate_method(method, agency):
    if not method.is_active or (method.agency_id and method.agency_id != agency.id):
        raise ValidationError("The payment method is unavailable.")


@transaction.atomic
def post_transaction(
    *,
    agency,
    actor,
    booking_id,
    kind,
    amount,
    currency,
    booking_exchange_rate,
    payment_method,
    transaction_date,
    reference="",
    notes="",
    allocations=None,
):
    booking = (
        Booking.objects.select_for_update()
        # source_quote is nullable; locking through this relation creates a LEFT OUTER JOIN
        # and PostgreSQL rejects FOR UPDATE on the nullable side of that join.
        .select_related("currency", "accounting_currency")
        .get(pk=booking_id, agency=agency)
    )
    if kind not in {FinancialTransaction.Kind.PAYMENT, FinancialTransaction.Kind.REFUND}:
        raise ValidationError("Only payments and refunds can be posted directly.")
    if kind == FinancialTransaction.Kind.PAYMENT and booking.status == Booking.Status.CANCELLED:
        raise ValidationError("Payments cannot be posted to a cancelled booking.")
    if kind == FinancialTransaction.Kind.PAYMENT:
        from bookings.readiness import payment_issues

        issues = payment_issues(booking)
        if issues:
            raise ValidationError(issues)
    _validate_method(payment_method, agency)
    amount = Decimal(amount)
    rate = Decimal(booking_exchange_rate)
    if amount <= 0 or rate <= 0:
        raise ValidationError("Amount and exchange rate must be greater than zero.")
    if currency.pk == booking.currency_id and rate != Decimal("1"):
        raise ValidationError("Same-currency exchange rate must equal 1.")
    booking_amount = quantize_money(amount * rate, booking.currency)
    accounting_amount = quantize_money(
        booking_amount * booking.accounting_exchange_rate,
        booking.accounting_currency,
    )
    summary = booking_financial_summary(booking)
    if kind == FinancialTransaction.Kind.PAYMENT and booking_amount > summary["remaining_amount"]:
        raise ValidationError("Payment exceeds the remaining booking balance.")
    if kind == FinancialTransaction.Kind.REFUND and booking_amount > summary["paid_amount"]:
        raise ValidationError("Refund exceeds the net amount paid.")
    prefix = "PAY" if kind == FinancialTransaction.Kind.PAYMENT else "REF"
    entry = FinancialTransaction(
        agency=agency,
        branch=booking.branch,
        booking=booking,
        number=f"{prefix}-{transaction_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
        kind=kind,
        amount=amount,
        currency=currency,
        booking_exchange_rate=rate,
        booking_amount=booking_amount,
        booking_currency=booking.currency,
        accounting_amount=accounting_amount,
        accounting_currency=booking.accounting_currency,
        payment_method=payment_method,
        transaction_date=transaction_date,
        reference=reference,
        notes=notes,
        created_by=actor,
    )
    entry.full_clean()
    entry.save()
    allocations = allocations or []
    allocation_total = sum((Decimal(item["amount"]) for item in allocations), Decimal("0"))
    if allocations and allocation_total != booking_amount:
        raise ValidationError("Traveler allocations must equal the payment in booking currency.")
    traveler_ids = [item["booking_traveler"] for item in allocations]
    if len(traveler_ids) != len(set(traveler_ids)):
        raise ValidationError("Each traveler may be allocated only once per transaction.")
    valid_ids = set(booking.travelers.filter(pk__in=traveler_ids).values_list("pk", flat=True))
    if valid_ids != set(traveler_ids):
        raise ValidationError("A payment allocation traveler belongs to another booking.")
    PaymentAllocation.objects.bulk_create(
        [
            PaymentAllocation(
                transaction=entry,
                booking_traveler_id=item["booking_traveler"],
                amount=item["amount"],
            )
            for item in allocations
        ]
    )
    return entry


@transaction.atomic
def reverse_transaction(*, agency, actor, transaction_id, transaction_date, reason):
    original = (
        FinancialTransaction.objects.select_for_update()
        .select_related(
            "booking",
            "branch",
            "currency",
            "booking_currency",
            "accounting_currency",
            "payment_method",
        )
        .get(pk=transaction_id, agency=agency)
    )
    if original.kind == FinancialTransaction.Kind.REVERSAL:
        raise ValidationError("A reversal cannot itself be reversed.")
    if hasattr(original, "reversal"):
        raise ValidationError("This transaction has already been reversed.")
    if not reason.strip():
        raise ValidationError("A reversal reason is required.")
    reversal = FinancialTransaction(
        agency=agency,
        branch=original.branch,
        booking=original.booking,
        number=f"REV-{transaction_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
        kind=FinancialTransaction.Kind.REVERSAL,
        amount=original.amount,
        currency=original.currency,
        booking_exchange_rate=original.booking_exchange_rate,
        booking_amount=original.booking_amount,
        booking_currency=original.booking_currency,
        accounting_amount=original.accounting_amount,
        accounting_currency=original.accounting_currency,
        payment_method=original.payment_method,
        transaction_date=transaction_date,
        reference=original.number,
        notes=reason.strip(),
        reverses=original,
        created_by=actor,
    )
    reversal.full_clean()
    reversal.save()
    PaymentAllocation.objects.bulk_create(
        [
            PaymentAllocation(
                transaction=reversal,
                booking_traveler=allocation.booking_traveler,
                amount=allocation.amount,
            )
            for allocation in original.traveler_allocations.all()
        ]
    )
    return reversal


@transaction.atomic
def post_expense_payment(
    *,
    agency,
    actor,
    expense_id,
    amount,
    currency,
    exchange_rate,
    payment_method,
    payment_date,
    reference="",
    notes="",
):
    expense = (
        TripExpense.objects.select_for_update()
        .select_related("currency")
        .get(pk=expense_id, agency=agency)
    )
    if expense.status == TripExpense.Status.CANCELLED:
        raise ValidationError("Payments cannot be posted to a cancelled expense.")
    _validate_method(payment_method, agency)
    amount = Decimal(amount)
    rate = Decimal(exchange_rate)
    if amount <= 0 or rate <= 0:
        raise ValidationError("Amount and exchange rate must be greater than zero.")
    if currency.pk == expense.currency_id and rate != Decimal("1"):
        raise ValidationError("Same-currency exchange rate must equal 1.")
    expense_amount = quantize_money(amount * rate, expense.currency)
    if expense_amount > expense.remaining_amount:
        raise ValidationError("Payment exceeds the remaining expense balance.")
    entry = ExpensePayment(
        agency=agency,
        expense=expense,
        number=f"EXP-{payment_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
        kind=ExpensePayment.Kind.PAYMENT,
        amount=amount,
        currency=currency,
        exchange_rate=rate,
        expense_amount=expense_amount,
        payment_method=payment_method,
        payment_date=payment_date,
        reference=reference,
        notes=notes,
        created_by=actor,
    )
    entry.full_clean()
    entry.save()
    return entry


@transaction.atomic
def reverse_expense_payment(*, agency, actor, payment_id, payment_date, reason):
    original = (
        ExpensePayment.objects.select_for_update()
        .select_related("expense", "currency", "payment_method")
        .get(pk=payment_id, agency=agency)
    )
    if original.kind == ExpensePayment.Kind.REVERSAL:
        raise ValidationError("A reversal cannot itself be reversed.")
    if hasattr(original, "reversal"):
        raise ValidationError("This expense payment has already been reversed.")
    if not reason.strip():
        raise ValidationError("A reversal reason is required.")
    entry = ExpensePayment(
        agency=agency,
        expense=original.expense,
        number=f"XRV-{payment_date:%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
        kind=ExpensePayment.Kind.REVERSAL,
        amount=original.amount,
        currency=original.currency,
        exchange_rate=original.exchange_rate,
        expense_amount=original.expense_amount,
        payment_method=original.payment_method,
        payment_date=payment_date,
        reference=original.number,
        notes=reason.strip(),
        reverses=original,
        created_by=actor,
    )
    entry.full_clean()
    entry.save()
    return entry
