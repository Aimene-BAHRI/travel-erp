from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking
from finance.models import TripExpense
from trips.models import Trip, TripClosingItem, TripTransport

from .models import Notification, NotificationRule


def notify_agency(*, agency, branch, event, title, message, target_url, dedupe_key, severity="INFO"):
    rule, _ = NotificationRule.objects.get_or_create(agency=agency, event=event)
    if not rule.is_enabled:
        return
    users = User.objects.filter(agency=agency, is_active=True)
    if rule.branch_only:
        users = users.filter(Q(branch=branch) | Q(branch__isnull=True))
    for user in users:
        notification, _ = Notification.objects.get_or_create(
            recipient=user,
            dedupe_key=dedupe_key,
            defaults={
                "severity": severity,
                "agency": agency,
                "branch": branch,
                "event": event,
                "title": title,
                "message": message,
                "target_url": target_url,
            },
        )
        if notification.message != message or notification.title != title or notification.severity != severity:
            notification.message, notification.title, notification.severity = message, title, severity
            notification.save(update_fields=["message", "title", "severity"])
        if notification.resolved_at:
            notification.resolved_at = None
            notification.read_at = None
            notification.save(update_fields=["resolved_at", "read_at"])


def sync_notifications(user):
    today = timezone.localdate()
    for event in NotificationRule.Event:
        NotificationRule.objects.get_or_create(agency=user.agency, event=event)
    rules = {
        r.event: r for r in NotificationRule.objects.filter(agency=user.agency, is_enabled=True)
    }
    active = set()
    _trip_alerts(user, rules, today, active)
    _booking_alerts(user, rules, today, active)
    _readiness_alerts(user, rules, today, active)
    _supplier_alerts(user, rules, today, active)
    _closing_task_alerts(user, rules, today, active)
    _transport_alerts(user, rules, today, active)
    scanner_events = [
        NotificationRule.Event.READINESS,
        NotificationRule.Event.TRIP_DEPARTURE,
        NotificationRule.Event.TRIP_CLOSING,
        NotificationRule.Event.BOOKING_BALANCE,
        NotificationRule.Event.PASSPORT_ATTENTION,
        NotificationRule.Event.ROOM_ALLOCATION,
        NotificationRule.Event.SUPPLIER_DUE,
        NotificationRule.Event.CLOSING_OVERDUE,
        NotificationRule.Event.TRANSPORT_DETAILS,
    ]
    stale = Notification.objects.filter(
        agency=user.agency, event__in=scanner_events, resolved_at__isnull=True
    ).exclude(dedupe_key__in=active)
    stale.update(resolved_at=timezone.now(), read_at=timezone.now())


def _trip_alerts(user, rules, today, active):
    rule = rules.get(NotificationRule.Event.TRIP_DEPARTURE)
    if rule:
        trips = Trip.objects.filter(
            agency=user.agency,
            departure_date__range=(today, today + timedelta(days=rule.lead_days)),
        ).exclude(status__in=[Trip.Status.COMPLETED, Trip.Status.CANCELLED])
        for trip in trips:
            active.add(f"{rule.event}:{trip.pk}")
            notify_agency(
                agency=user.agency,
                branch=trip.branch,
                event=rule.event,
                title="Trip departure approaching",
                message=f"{trip.name} departs on {trip.departure_date}.",
                target_url=f"/trips/{trip.pk}",
                dedupe_key=f"{rule.event}:{trip.pk}",
            )
    rule = rules.get(NotificationRule.Event.TRIP_CLOSING)
    if rule:
        trips = Trip.objects.filter(
            agency=user.agency,
            return_date__lt=today,
            closing_status__in=[
                Trip.ClosingStatus.NOT_DUE,
                Trip.ClosingStatus.PENDING,
                Trip.ClosingStatus.READY,
            ],
        ).exclude(status=Trip.Status.CANCELLED)
        for trip in trips:
            active.add(f"{rule.event}:{trip.pk}")
            notify_agency(
                agency=user.agency,
                branch=trip.branch,
                event=rule.event,
                title="Trip requires closing",
                message=f"{trip.name} has returned and requires closing.",
                target_url=f"/trips/{trip.pk}",
                dedupe_key=f"{rule.event}:{trip.pk}",
            )


def _booking_alerts(user, rules, today, active):
    booking_rules = [
        rules.get(x)
        for x in [
            NotificationRule.Event.BOOKING_BALANCE,
            NotificationRule.Event.PASSPORT_ATTENTION,
            NotificationRule.Event.ROOM_ALLOCATION,
        ]
    ]
    lead = max([rule.lead_days for rule in booking_rules if rule] or [0])
    bookings = (
        Booking.objects.filter(
            agency=user.agency,
            status=Booking.Status.CONFIRMED,
            trip__departure_date__range=(today, today + timedelta(days=lead)),
        )
        .select_related("branch", "trip")
        .prefetch_related(
            "financial_transactions__reverses",
            "travelers__traveler__passports",
            "travelers__trip_room_assignments",
        )
    )
    for booking in bookings:
        balance_rule = rules.get(NotificationRule.Event.BOOKING_BALANCE)
        paid = sum((x.signed_booking_amount for x in booking.financial_transactions.all()), 0)
        if (
            balance_rule
            and booking.total_amount > paid
            and booking.trip.departure_date <= today + timedelta(days=balance_rule.lead_days)
        ):
            active.add(f"{balance_rule.event}:{booking.pk}")
            notify_agency(
                agency=user.agency,
                branch=booking.branch,
                event=balance_rule.event,
                title="Booking balance outstanding",
                message=(
                    f"{booking.code}: {booking.total_amount - paid} "
                    f"{booking.currency_id} remaining."
                ),
                target_url=f"/bookings/{booking.pk}",
                dedupe_key=f"{balance_rule.event}:{booking.pk}",
            )


def _supplier_alerts(user, rules, today, active):
    rule = rules.get(NotificationRule.Event.SUPPLIER_DUE)
    if not rule:
        return
    expenses = (
        TripExpense.objects.filter(
            agency=user.agency, due_date__range=(today, today + timedelta(days=rule.lead_days))
        )
        .exclude(status=TripExpense.Status.CANCELLED)
        .select_related("branch")
        .prefetch_related("payments__reverses")
    )
    for expense in expenses:
        if expense.remaining_amount > 0:
            active.add(f"{rule.event}:{expense.pk}")
            notify_agency(
                agency=user.agency,
                branch=expense.branch,
                event=rule.event,
                title="Supplier expense due",
                message=(
                    f"{expense.description}: {expense.remaining_amount} "
                    f"{expense.currency_id} remaining."
                ),
                target_url=f"/trips/{expense.trip_id}",
                dedupe_key=f"{rule.event}:{expense.pk}",
            )


def _closing_task_alerts(user, rules, today, active):
    rule = rules.get(NotificationRule.Event.CLOSING_OVERDUE)
    if not rule:
        return
    items = TripClosingItem.objects.filter(
        trip__agency=user.agency, state=TripClosingItem.State.PENDING, due_date__lt=today
    ).select_related("trip__branch", "assigned_to")
    for item in items:
        key = f"{rule.event}:{item.pk}"
        active.add(key)
        if item.assigned_to_id:
            Notification.objects.get_or_create(
                recipient=item.assigned_to,
                dedupe_key=key,
                defaults={
                    "agency": user.agency,
                    "branch": item.trip.branch,
                    "event": rule.event,
                    "title": "Trip closing task overdue",
                    "message": f"{item.get_key_display()} is overdue for {item.trip.name}.",
                    "target_url": f"/trips/{item.trip_id}",
                },
            )
        else:
            notify_agency(
                agency=user.agency,
                branch=item.trip.branch,
                event=rule.event,
                title="Trip closing task overdue",
                message=f"{item.get_key_display()} is overdue for {item.trip.name}.",
                target_url=f"/trips/{item.trip_id}",
                dedupe_key=key,
            )


def _transport_alerts(user, rules, today, active):
    rule = rules.get(NotificationRule.Event.TRANSPORT_DETAILS)
    if not rule:
        return
    transports = (
        TripTransport.objects.filter(
            trip__agency=user.agency,
            departure_at__date__range=(today, today + timedelta(days=rule.lead_days)),
        )
        .exclude(trip__status__in=[Trip.Status.COMPLETED, Trip.Status.CANCELLED])
        .select_related("trip__branch", "origin_city", "destination_city")
    )
    for transport in transports:
        missing = [
            label
            for label, value in (
                ("reference", transport.reference),
                ("vehicle details", transport.vehicle_details),
                ("vehicle number", transport.vehicle_number),
            )
            if not value.strip()
        ]
        if not missing:
            continue
        key = f"{rule.event}:{transport.pk}"
        active.add(key)
        notify_agency(
            agency=user.agency,
            branch=transport.trip.branch,
            event=rule.event,
            title="Ground transport details incomplete",
            message=(
                f"{transport.trip.name}: {transport.get_mode_display()} from "
                f"{transport.origin_city.name} to {transport.destination_city.name} "
                f"departs on {transport.departure_at:%Y-%m-%d}. Missing {', '.join(missing)}."
            ),
            target_url=f"/trips/{transport.trip_id}",
            dedupe_key=key,
        )


def _readiness_alerts(user, rules, today, active):
    from bookings.readiness import trip_readiness
    rule = rules.get(NotificationRule.Event.READINESS)
    if not rule:
        return
    trips = Trip.objects.filter(agency=user.agency).exclude(status__in=[Trip.Status.CANCELLED, Trip.Status.COMPLETED])
    for trip in trips:
        report = trip_readiness(trip)
        count, seats = report["travelers"], report["seats"]
        if not count["total"]:
            continue
        key = f"READINESS:{trip.pk}"
        active.add(key)
        remaining = seats["remaining"]
        severity = "ERROR" if seats["overbooked_places"] or any(report["invalid"].values()) or report["beds"]["over_capacity_rooms"] else "WARNING" if report["data_quality"]["incomplete"] or (remaining is not None and remaining <= 2) else "SUCCESS" if report["is_ready"] else "INFO"
        message = f"{trip.name}: {count['total']} travelers ({count['adt']} ADT, {count['chd']} CHD, {count['inf']} INF). {seats['occupied']}/{seats['capacity'] if seats['capacity'] is not None else 'unlimited'} seats occupied; {remaining if remaining is not None else 'unlimited'} remaining. {report['data_quality']['incomplete']} incomplete files; {report['missing']['passport']} missing passports; {report['invalid']['passport']} invalid passports; {report['missing']['room']} missing room allocations; {report['missing']['price']} missing prices."
        if report["errors"]:
            message += " " + " ".join(report["errors"])
        notify_agency(agency=trip.agency, branch=trip.branch, event=NotificationRule.Event.READINESS, title="Trip ready" if report["is_ready"] else "Trip readiness requires attention", message=message, target_url=f"/trips/{trip.pk}", dedupe_key=key, severity=severity)
