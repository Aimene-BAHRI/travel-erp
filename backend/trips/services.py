from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from bookings.models import Booking
from finance.models import TripExpense

from .models import Trip, TripAllocationRoom, TripClosingItem, TripRoomAssignment, TripStop

ALLOWED_TRIP_TRANSITIONS = {
    Trip.Status.DRAFT: {Trip.Status.OPEN, Trip.Status.CANCELLED},
    Trip.Status.OPEN: {Trip.Status.CLOSED, Trip.Status.CANCELLED},
    Trip.Status.CLOSED: {Trip.Status.OPEN, Trip.Status.DEPARTED, Trip.Status.CANCELLED},
    Trip.Status.DEPARTED: {Trip.Status.COMPLETED},
    Trip.Status.COMPLETED: set(),
    Trip.Status.CANCELLED: set(),
}


def validate_itinerary(trip):
    stops = list(trip.stops.select_related("city").order_by("order"))
    if not stops:
        raise ValidationError("A trip requires at least one itinerary stop.")
    previous = None
    for expected_order, stop in enumerate(stops, start=1):
        if stop.order != expected_order:
            raise ValidationError("Itinerary stop order must be contiguous and start at 1.")
        stop.full_clean()
        if previous and stop.arrival_date < previous.departure_date:
            raise ValidationError("Itinerary stops cannot overlap.")
        previous = stop
    return stops


@transaction.atomic
def transition_trip(*, trip_id, agency, target_status):
    trip = Trip.objects.select_for_update().get(pk=trip_id, agency=agency)
    if target_status not in ALLOWED_TRIP_TRANSITIONS[trip.status]:
        raise ValidationError(f"Trip cannot transition from {trip.status} to {target_status}.")
    if target_status == Trip.Status.OPEN:
        validate_itinerary(trip)
    trip.status = target_status
    trip.save(update_fields=["status", "updated_at"])
    return trip


def _ensure_closing_items(trip):
    existing = set(trip.closing_items.values_list("key", flat=True))
    TripClosingItem.objects.bulk_create(
        [TripClosingItem(trip=trip, key=key) for key in TripClosingItem.Key if key not in existing]
    )


@transaction.atomic
def start_trip_closing(*, trip_id, agency):
    trip = Trip.objects.select_for_update().get(pk=trip_id, agency=agency)
    if trip.status == Trip.Status.CANCELLED:
        raise ValidationError("A cancelled trip cannot enter closing.")
    if trip.return_date >= timezone.localdate() and trip.status != Trip.Status.COMPLETED:
        raise ValidationError("Trip closing starts after the return date or trip completion.")
    if trip.closing_status == Trip.ClosingStatus.NOT_DUE:
        trip.closing_status = Trip.ClosingStatus.PENDING
        trip.closing_started_at = timezone.now()
        trip.save(update_fields=["closing_status", "closing_started_at", "updated_at"])
    _ensure_closing_items(trip)
    return trip


def trip_closing_summary(trip):
    if (
        trip.closing_status == Trip.ClosingStatus.NOT_DUE
        and trip.status != Trip.Status.CANCELLED
        and (trip.return_date < timezone.localdate() or trip.status == Trip.Status.COMPLETED)
    ):
        trip = start_trip_closing(trip_id=trip.pk, agency=trip.agency)
    if trip.closing_status != Trip.ClosingStatus.NOT_DUE:
        _ensure_closing_items(trip)

    items = list(trip.closing_items.select_related("completed_by").all())
    complete_states = {TripClosingItem.State.COMPLETED, TripClosingItem.State.NOT_REQUIRED}
    completed_count = sum(item.state in complete_states for item in items)

    bookings = list(
        trip.bookings.exclude(status=Booking.Status.CANCELLED).prefetch_related(
            "financial_transactions__reverses"
        )
    )
    revenue = sum((booking.accounting_total_amount for booking in bookings), Decimal("0"))
    collected = sum(
        (
            entry.signed_accounting_amount
            for booking in bookings
            for entry in booking.financial_transactions.all()
        ),
        Decimal("0"),
    )
    expenses_by_currency = {}
    supplier_outstanding_by_currency = {}
    for expense in trip.expenses.exclude(status=TripExpense.Status.CANCELLED).prefetch_related(
        "payments__reverses"
    ):
        code = expense.currency_id
        expenses_by_currency[code] = expenses_by_currency.get(code, Decimal("0")) + expense.amount
        supplier_outstanding_by_currency[code] = (
            supplier_outstanding_by_currency.get(code, Decimal("0")) + expense.remaining_amount
        )
    accounting_currency = bookings[0].accounting_currency_id if bookings else ""
    comparable_expenses = expenses_by_currency.get(accounting_currency, Decimal("0"))
    has_foreign_expenses = any(
        currency != accounting_currency and amount
        for currency, amount in expenses_by_currency.items()
    )

    return {
        "status": trip.closing_status,
        "can_start": (
            trip.return_date < timezone.localdate() or trip.status == Trip.Status.COMPLETED
        ),
        "completed_count": completed_count,
        "total_count": len(items),
        "is_ready": bool(items) and completed_count == len(items),
        "closed_at": trip.closed_at,
        "closed_by": trip.closed_by.get_full_name() or trip.closed_by.email
        if trip.closed_by_id
        else "",
        "items": items,
        "financials": {
            "accounting_currency": accounting_currency,
            "revenue": revenue,
            "collected": collected,
            "customer_outstanding": revenue - collected,
            "expenses_by_currency": expenses_by_currency,
            "supplier_outstanding_by_currency": supplier_outstanding_by_currency,
            "profit_loss": None if has_foreign_expenses else revenue - comparable_expenses,
            "profit_loss_note": (
                "Convert foreign-currency expenses before calculating final profit and loss."
                if has_foreign_expenses
                else ""
            ),
            "document_count": trip.document_links.count(),
        },
    }


@transaction.atomic
def update_trip_closing_item(
    *, trip_id, agency, actor, key, state, notes, assigned_to=None, due_date=None
):
    trip = start_trip_closing(trip_id=trip_id, agency=agency)
    if trip.closing_status == Trip.ClosingStatus.CLOSED:
        raise ValidationError("Reopen the trip closing before changing checklist items.")
    item = TripClosingItem.objects.select_for_update().get(trip=trip, key=key)
    item.state = state
    item.notes = notes
    if assigned_to:
        from accounts.models import User

        item.assigned_to = User.objects.get(pk=assigned_to, agency=agency, is_active=True)
    else:
        item.assigned_to = None
    item.due_date = due_date
    if state in {TripClosingItem.State.COMPLETED, TripClosingItem.State.NOT_REQUIRED}:
        item.completed_by = actor
        item.completed_at = timezone.now()
    else:
        item.completed_by = None
        item.completed_at = None
    item.full_clean()
    item.save()
    summary = trip_closing_summary(trip)
    target = Trip.ClosingStatus.READY if summary["is_ready"] else Trip.ClosingStatus.PENDING
    if trip.closing_status != target:
        trip.closing_status = target
        trip.save(update_fields=["closing_status", "updated_at"])
    return trip


@transaction.atomic
def close_trip(*, trip_id, agency, actor):
    trip = Trip.objects.select_for_update().get(pk=trip_id, agency=agency)
    summary = trip_closing_summary(trip)
    if not summary["is_ready"]:
        raise ValidationError("Every required closing item must be completed or not required.")
    final_report = trip.closing_items.get(key=TripClosingItem.Key.FINAL_REPORT)
    if not final_report.notes.strip() and not trip.document_links.exists():
        raise ValidationError("Add final-report notes or archive a final report document.")
    trip.closing_status = Trip.ClosingStatus.CLOSED
    trip.closed_at = timezone.now()
    trip.closed_by = actor
    trip.save(update_fields=["closing_status", "closed_at", "closed_by", "updated_at"])
    return trip


@transaction.atomic
def reopen_trip_closing(*, trip_id, agency):
    trip = Trip.objects.select_for_update().get(pk=trip_id, agency=agency)
    if trip.closing_status != Trip.ClosingStatus.CLOSED:
        raise ValidationError("Only a closed trip can be reopened.")
    trip.closing_status = Trip.ClosingStatus.PENDING
    trip.closed_at = None
    trip.closed_by = None
    trip.save(update_fields=["closing_status", "closed_at", "closed_by", "updated_at"])
    return trip


@transaction.atomic
def save_trip_stop(*, instance=None, trip, **data):
    list(TripStop.objects.select_for_update().filter(trip=trip).values_list("pk", flat=True))
    if instance is None:
        instance = TripStop(trip=trip)
    for field, value in data.items():
        setattr(instance, field, value)
    instance.full_clean()
    instance.save()
    validate_itinerary(trip)
    return instance


@transaction.atomic
def reorder_trip_stops(*, trip, ordered_ids):
    stops = list(TripStop.objects.select_for_update().filter(trip=trip))
    if {str(stop.pk) for stop in stops} != {str(item) for item in ordered_ids}:
        raise ValidationError("The reorder request must contain every stop exactly once.")
    by_id = {str(stop.pk): stop for stop in stops}
    TripStop.objects.filter(trip=trip).update(order=models.F("order") + 10000)
    for order, stop_id in enumerate(ordered_ids, start=1):
        stop = by_id[str(stop_id)]
        stop.order = order
        stop.save(update_fields=["order"])
    validate_itinerary(trip)
    return list(trip.stops.select_related("city").order_by("order"))


@transaction.atomic
def assign_traveler_to_room(*, room_id, booking_traveler, agency, actor, bed_number=None):
    room = (
        TripAllocationRoom.objects.select_for_update()
        .select_related("trip_hotel__stop__trip")
        .get(pk=room_id, trip_hotel__stop__trip__agency=agency)
    )
    from bookings.readiness import require_room_ready

    require_room_ready(booking_traveler)
    stop = room.trip_hotel.stop
    if booking_traveler.booking.trip_id != stop.trip_id:
        raise ValidationError("Traveler and room must belong to the same trip.")
    list(
        TripRoomAssignment.objects.select_for_update()
        .filter(stop=stop)
        .values_list("pk", flat=True)
    )
    occupied = set(
        room.assignments.exclude(booking_traveler=booking_traveler).values_list(
            "bed_number", flat=True
        )
    )
    if bed_number is None:
        bed_number = next(
            (number for number in range(1, room.capacity + 1) if number not in occupied), None
        )
    if bed_number is None or bed_number in occupied:
        raise ValidationError("The selected room has no free bed at that position.")
    assignment, _ = TripRoomAssignment.objects.update_or_create(
        stop=stop,
        booking_traveler=booking_traveler,
        defaults={"room": room, "bed_number": bed_number, "assigned_by": actor},
    )
    from bookings.readiness import room_assignment_issues, required_stops
    allowed = required_stops(booking_traveler, list(stop.trip.stops.filter(hotels__isnull=False).distinct()))
    if stop.pk not in {item.pk for item in allowed}:
        raise ValidationError("This stay is not included in the traveler's service.")
    issues = [issue for issue in room_assignment_issues(booking_traveler) if "incomplete" not in issue]
    if issues:
        raise ValidationError(issues)
    assignment.full_clean()
    assignment.save()
    return assignment
