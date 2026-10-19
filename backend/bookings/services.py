import hashlib
import json
import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from customers.models import Customer
from pricing.models import Quote, QuoteLine, TripHotelPrice
from reference.models import AgencyCurrency
from travelers.models import Traveler
from travelers.rules import passenger_category_code, passport_validity

from .models import (
    Booking,
    BookingAccommodation,
    BookingDiscount,
    BookingFlight,
    BookingRequest,
    BookingRoomGroup,
    BookingRoomTraveler,
    BookingSnapshot,
    BookingTraveler,
    BookingTravelerCharge,
)


def _booking_code(agency):
    prefix = timezone.localdate().strftime("B-%Y%m%d")
    while True:
        code = f"{prefix}-{uuid.uuid4().hex[:6].upper()}"
        if not Booking.objects.filter(agency=agency, code=code).exists():
            return code


def _sync_draft_total(booking):
    charges = BookingTravelerCharge.objects.filter(
        booking_traveler__booking=booking
    ).prefetch_related("discounts")
    total = sum((charge.final_amount for charge in charges), Decimal("0")).quantize(
        Decimal("0.0001")
    )
    from .commercial import extra_total
    total += extra_total(booking)
    accounting_total = (total * booking.accounting_exchange_rate).quantize(Decimal("0.0001"))
    Booking.objects.filter(pk=booking.pk, status=Booking.Status.DRAFT).update(
        total_amount=total, accounting_total_amount=accounting_total
    )
    booking.total_amount = total
    booking.accounting_total_amount = accounting_total
    return booking


def _snapshot_payload(booking, quote, accommodations, flights):
    return {
        "schema_version": 1,
        "booking": {
            "id": str(booking.pk),
            "code": booking.code,
            "agency": {"id": str(booking.agency_id), "name": booking.agency.name},
            "branch": {"id": str(booking.branch_id), "name": booking.branch.name},
            "customer": {
                "id": str(booking.customer_id),
                "name": booking.customer.display_name,
            },
            "trip": {
                "id": str(booking.trip_id),
                "code": booking.trip.code,
                "name": booking.trip.name,
            },
            "currency": booking.currency_id,
            "expected_travelers": booking.expected_travelers,
            "total_amount": str(booking.total_amount),
            "accounting_currency": booking.accounting_currency_id,
            "accounting_total_amount": str(booking.accounting_total_amount),
        },
        "source_quote": {
            "id": str(quote.pk),
            "code": quote.code,
            "snapshot_sha256": quote.snapshot.sha256,
            "payload": quote.snapshot.payload,
        }
        if quote
        else None,
        "accommodations": [
            {
                "id": str(item.pk),
                "trip_hotel_id": str(item.trip_hotel_id),
                "hotel_name": item.trip_hotel.hotel.name,
                "room_type_id": str(item.room_type_id),
                "room_type_name": item.room_type.name,
                "passenger_category_id": str(item.passenger_category_id),
                "passenger_category_name": item.passenger_category.name,
                "bed_basis": item.bed_basis,
                "quantity": item.quantity,
                "unit_amount": str(item.unit_amount),
                "total_amount": str(item.total_amount),
                "currency": item.currency_id,
                "source_quote_line_id": str(item.source_quote_line_id)
                if item.source_quote_line_id
                else None,
            }
            for item in accommodations
        ],
        "flights": [
            {
                "id": str(item.trip_flight_id),
                "order": item.trip_flight.order,
                "flight_number": item.trip_flight.flight_number,
                "origin_airport_code": item.trip_flight.origin_airport_code,
                "destination_airport_code": item.trip_flight.destination_airport_code,
                "departure_at": item.trip_flight.departure_at.isoformat(),
                "arrival_at": item.trip_flight.arrival_at.isoformat(),
            }
            for item in flights
        ],
    }


@transaction.atomic
def create_booking_from_quote(*, quote_id, agency, actor, code=""):
    quote = (
        Quote.objects.select_for_update(of=("self",))
        .select_related(
            "agency",
            "branch",
            "customer",
            "trip",
            "currency",
            "accounting_currency",
            "snapshot",
        )
        .get(pk=quote_id, agency=agency)
    )
    if quote.status != Quote.Status.ACCEPTED:
        raise ValidationError("Only accepted quotes can become bookings.")
    if Booking.objects.filter(source_quote=quote).exists():
        raise ValidationError("This quote already has a booking.")
    hotel_lines = list(
        QuoteLine.objects.select_for_update(of=("self",))
        .filter(quote=quote, kind=QuoteLine.Kind.HOTEL)
        .select_related(
            "hotel_price__trip_hotel__hotel",
            "hotel_price__room_type",
            "hotel_price__passenger_category",
        )
    )
    if not hotel_lines:
        raise ValidationError("A booking requires at least one sold accommodation line.")

    booking = Booking(
        agency=quote.agency,
        branch=quote.branch,
        code=code or _booking_code(agency),
        customer=quote.customer,
        trip=quote.trip,
        source_quote=quote,
        currency=quote.currency,
        total_amount=quote.snapshot.quote_total,
        accounting_currency=quote.accounting_currency,
        accounting_exchange_rate=quote.accounting_exchange_rate,
        accounting_total_amount=quote.snapshot.accounting_total,
        created_by=actor,
    )
    booking.full_clean()
    booking.save()

    accommodations = []
    for line in hotel_lines:
        price = line.hotel_price
        if price is None:
            raise ValidationError("A hotel quote line has no recoverable accommodation source.")
        accommodation = BookingAccommodation(
            booking=booking,
            trip_hotel=price.trip_hotel,
            room_type=price.room_type,
            passenger_category=price.passenger_category,
            bed_basis=price.bed_basis,
            quantity=line.quantity,
            unit_amount=line.unit_amount,
            total_amount=line.total_amount,
            currency=quote.currency,
            source_quote_line=line,
        )
        accommodation.full_clean()
        accommodation.save()
        accommodations.append(accommodation)

    flights = [
        BookingFlight.objects.create(booking=booking, trip_flight=trip_flight)
        for trip_flight in quote.trip.flights.order_by("order")
    ]
    _set_sold_group_size(booking, accommodations)
    payload = _snapshot_payload(booking, quote, accommodations, flights)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    snapshot = BookingSnapshot(
        booking=booking,
        payload=payload,
        sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )
    snapshot.full_clean()
    snapshot.save()
    return booking


@transaction.atomic
def create_direct_booking(
    *,
    agency,
    actor,
    branch,
    trip,
    code,
    currency,
    accounting_currency,
    accounting_exchange_rate,
    price_lines,
    customer=None,
    new_customer=None,
    notes="",
):
    if not price_lines:
        raise ValidationError("A direct booking requires at least one accommodation price.")
    if customer is None:
        customer = Customer(agency=agency, branch=branch, created_by=actor, **new_customer)
        customer.full_clean()
        customer.save()
    for name, value in [("branch", branch), ("customer", customer), ("trip", trip)]:
        if value.agency_id != agency.id:
            raise ValidationError(f"The {name} must belong to the same agency.")
    price_ids = [line["price_id"] for line in price_lines]
    prices = {
        str(item.pk): item
        for item in TripHotelPrice.objects.select_for_update(of=("self",))
        .select_related(
            "trip_hotel__stop__trip", "trip_hotel__hotel", "room_type", "passenger_category"
        )
        .filter(pk__in=price_ids, agency=agency)
    }
    if len(prices) != len(set(map(str, price_ids))):
        raise ValidationError("One or more hotel prices are unavailable.")
    total = Decimal("0")
    prepared = []
    for line in price_lines:
        price = prices[str(line["price_id"])]
        if price.trip_hotel.stop.trip_id != trip.id:
            raise ValidationError("Every hotel price must belong to the selected trip.")
        quantity = line["quantity"]
        unit_amount = (price.amount * line["exchange_rate"]).quantize(Decimal("0.0001"))
        line_total = (unit_amount * quantity).quantize(Decimal("0.0001"))
        total += line_total
        prepared.append((price, quantity, unit_amount, line_total))
    booking = Booking(
        agency=agency,
        branch=branch,
        code=code or _booking_code(agency),
        customer=customer,
        trip=trip,
        source_quote=None,
        currency=currency,
        total_amount=total,
        accounting_currency=accounting_currency,
        accounting_exchange_rate=accounting_exchange_rate,
        accounting_total_amount=(total * accounting_exchange_rate).quantize(Decimal("0.0001")),
        notes=notes,
        created_by=actor,
    )
    booking.full_clean()
    booking.save()
    accommodations = []
    for price, quantity, unit_amount, line_total in prepared:
        item = BookingAccommodation(
            booking=booking,
            trip_hotel=price.trip_hotel,
            room_type=price.room_type,
            passenger_category=price.passenger_category,
            bed_basis=price.bed_basis,
            quantity=quantity,
            unit_amount=unit_amount,
            total_amount=line_total,
            currency=currency,
            source_quote_line=None,
        )
        item.full_clean()
        item.save()
        accommodations.append(item)
    flights = [
        BookingFlight.objects.create(booking=booking, trip_flight=flight)
        for flight in trip.flights.order_by("order")
    ]
    _set_sold_group_size(booking, accommodations)
    payload = _snapshot_payload(booking, None, accommodations, flights)
    payload["source"] = "DIRECT"
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    BookingSnapshot.objects.create(
        booking=booking,
        payload=payload,
        sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )
    return booking


@transaction.atomic
def create_booking_draft(
    *,
    agency,
    actor,
    branch,
    trip,
    currency,
    accounting_currency,
    accounting_exchange_rate,
    customer=None,
    new_customer=None,
    notes="",
    expected_travelers=1,
    partner=None,
    lead_source=None,
    source_detail='',
):
    if expected_travelers < 1:
        raise ValidationError("Expected travelers must be at least one.")
    if partner is not None:
        if partner.agency_id != agency.pk or not partner.is_active or partner.kind != "COMPANY":
            raise ValidationError("Select an active partner agency belonging to this agency.")
        if customer is not None or new_customer is not None:
            raise ValidationError("A partner booking uses the partner's contact details.")
        # Retain the existing customer-based financial interface, with an explicit partner source.
        previous = Booking.objects.filter(agency=agency, branch=branch, partner=partner).select_related("customer").first()
        customer = previous.customer if previous else None
        new_customer = {"kind": "COMPANY", "company_name": partner.name, "phone": partner.phone, "email": partner.email}
    if customer is None:
        customer = Customer(agency=agency, branch=branch, created_by=actor, **new_customer)
        customer.full_clean()
        customer.save()
    booking = Booking(
        agency=agency,
        branch=branch,
        code=_booking_code(agency),
        partner=partner,
        commercial_details=({'source': 'PARTNER' if partner else lead_source, 'source_detail': source_detail} if lead_source else {}),
        customer=customer,
        trip=trip,
        currency=currency,
        total_amount=Decimal("0"),
        accounting_currency=accounting_currency,
        accounting_total_amount=Decimal("0"),
        accounting_exchange_rate=accounting_exchange_rate,
        status=Booking.Status.DRAFT,
        expected_travelers=expected_travelers,
        notes=notes,
        created_by=actor,
    )
    booking.full_clean()
    booking.save()
    return booking


@transaction.atomic
def convert_booking_request_to_draft(*, request_id, agency, actor):
    booking_request = (
        BookingRequest.objects.select_for_update()
        .get(pk=request_id, agency=agency)
    )
    if booking_request.booking_id:
        return Booking.objects.get(pk=booking_request.booking_id, agency=agency)
    if booking_request.status == BookingRequest.Status.CONVERTED:
        raise ValidationError("This request is marked converted but has no linked booking.")
    if booking_request.calculated_currency_id is None:
        raise ValidationError("A request without a calculated currency cannot be converted.")

    accounting_setting = (
        AgencyCurrency.objects.filter(
            agency=agency, is_accounting=True, is_enabled=True
        )
        .select_related("currency")
        .first()
    )
    if accounting_setting is None:
        raise ValidationError("Configure an accounting currency before converting requests.")
    accounting_currency = accounting_setting.currency

    name_parts = booking_request.customer_name.strip().split(maxsplit=1)
    customer_data = {
        "first_name": name_parts[0] if name_parts else "Customer",
        "last_name": name_parts[1] if len(name_parts) > 1 else "",
        "phone": booking_request.phone,
        "email": booking_request.email,
        "notes": f"Created from booking request {booking_request.reference}.",
    }
    notes = (
        f"Converted from {booking_request.reference}. "
        f"Requested travelers: {booking_request.adults} adults, "
        f"{booking_request.children_with_bed} children with bed, "
        f"{booking_request.children_without_bed} children without bed, "
        f"{booking_request.infants} infants. "
        f"Submitted estimate: {booking_request.calculated_total or 'n/a'} "
        f"{booking_request.calculated_currency_id or ''}."
    )
    if booking_request.notes:
        notes = f"{notes}\n{booking_request.notes}"
    booking = create_booking_draft(
        agency=agency,
        actor=actor,
        branch=booking_request.trip.branch,
        trip=booking_request.trip,
        currency=booking_request.calculated_currency,
        accounting_currency=accounting_currency,
        accounting_exchange_rate=Decimal("1"),
        expected_travelers=(booking_request.adults + max(booking_request.children, booking_request.children_with_bed + booking_request.children_without_bed) + booking_request.infants),
        new_customer=customer_data,
        notes=notes,
    )
    booking_request.booking = booking
    booking_request.status = BookingRequest.Status.CONVERTED
    booking_request.save(update_fields=["booking", "status", "updated_at"])
    return booking


@transaction.atomic
def add_inline_booking_traveler(
    *,
    booking_id,
    agency,
    actor,
    first_name,
    last_name,
    bed_requirement,
    passenger_category=None,
    phone="",
    birth_date=None,
    gender=Traveler.Gender.UNSPECIFIED,
    is_customer_contact=False,
    notes="",
):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    if booking.status not in {Booking.Status.DRAFT, Booking.Status.CONFIRMED}:
        raise ValidationError("Travelers can only be added to draft or confirmed bookings.")
    if booking.status == Booking.Status.CONFIRMED and (
        not first_name.strip() or not last_name.strip() or birth_date is None
    ):
        raise ValidationError("First name, last name, and birth date are required.")
    if birth_date and birth_date > timezone.localdate():
        raise ValidationError("Birth date cannot be in the future.")
    if not (first_name.strip() or last_name.strip()):
        raise ValidationError("Enter at least a first or last name.")
    if birth_date:
        from reference.models import PassengerCategory

        code = passenger_category_code(birth_date, booking.trip.return_date)
        passenger_category = PassengerCategory.objects.get(
            code__iexact=code, is_system=True, is_active=True
        )
    if passenger_category is None:
        raise ValidationError("Birth date is required to determine the passenger category.")
    if booking.status == Booking.Status.CONFIRMED:
        bed_requirement = (
            BookingTraveler.BedRequirement.NOT_REQUIRED
            if passenger_category.code.upper() == "INF"
            else BookingTraveler.BedRequirement.REQUIRED
        )
    traveler = Traveler.objects.create(
        agency=agency,
        branch=booking.branch,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        phone=phone,
        birth_date=birth_date,
        gender=gender,
        created_by=actor,
    )
    return add_booking_traveler(
        booking_id=booking.pk,
        agency=agency,
        traveler=traveler,
        passenger_category=passenger_category,
        bed_requirement=bed_requirement,
        notes=notes,
        is_customer_contact=is_customer_contact,
    )


@transaction.atomic
def add_room_group(*, booking_id, agency, trip_hotel, room_type, label, capacity, notes=""):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    if booking.status != Booking.Status.DRAFT:
        raise ValidationError("Rooms can only be changed while the booking is a draft.")
    if trip_hotel.stop.trip_id != booking.trip_id or room_type.agency_id != agency.id:
        raise ValidationError("The hotel or room type is unavailable for this booking.")
    room = BookingRoomGroup(
        booking=booking,
        trip_hotel=trip_hotel,
        room_type=room_type,
        label=label,
        capacity=capacity,
        notes=notes,
    )
    room.full_clean()
    room.save()
    return room


@transaction.atomic
def assign_room_traveler(*, booking_id, room_id, booking_traveler_id, agency):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    room = BookingRoomGroup.objects.select_for_update().get(pk=room_id, booking=booking)
    traveler = BookingTraveler.objects.get(pk=booking_traveler_id, booking=booking)
    if booking.status != Booking.Status.DRAFT:
        raise ValidationError("Room assignments can only change on draft bookings.")
    from .readiness import require_room_ready

    require_room_ready(traveler)
    if room.traveler_assignments.count() >= room.capacity:
        raise ValidationError("This room has reached its traveler capacity.")
    if BookingRoomTraveler.objects.filter(
        booking_traveler=traveler,
        room_group__trip_hotel__stop=room.trip_hotel.stop,
    ).exists():
        raise ValidationError("This traveler already has a room for this itinerary stop.")
    return BookingRoomTraveler.objects.create(room_group=room, booking_traveler=traveler)


@transaction.atomic
def add_traveler_charge(
    *,
    booking_id,
    booking_traveler_id,
    agency,
    kind,
    description,
    base_amount,
    currency,
    source_price=None,
    notes="",
):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    traveler = BookingTraveler.objects.get(pk=booking_traveler_id, booking=booking)
    if booking.status != Booking.Status.DRAFT:
        raise ValidationError("Charges can only change on draft bookings.")
    if source_price and source_price.trip_hotel.stop.trip_id != booking.trip_id:
        raise ValidationError("The source price belongs to another trip.")
    if source_price and source_price.currency_id != booking.currency_id:
        raise ValidationError("The hotel price must use the booking currency.")
    charge = BookingTravelerCharge(
        booking_traveler=traveler,
        kind=kind,
        description=description,
        source_price=source_price,
        base_amount=base_amount,
        currency=currency,
        notes=notes,
    )
    charge.full_clean()
    charge.save()
    _sync_draft_total(booking)
    return charge


@transaction.atomic
def add_charge_discount(*, booking_id, charge_id, agency, actor, kind, value, reason):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    charge = BookingTravelerCharge.objects.select_related("booking_traveler").get(
        pk=charge_id, booking_traveler__booking=booking
    )
    if booking.status != Booking.Status.DRAFT:
        raise ValidationError("Discounts can only change on draft bookings.")
    amount = (
        value
        if kind == BookingDiscount.Kind.AMOUNT
        else (charge.base_amount * value / Decimal("100"))
    )
    if amount <= 0 or amount > charge.final_amount:
        raise ValidationError("The discount exceeds the remaining traveler charge.")
    discount = BookingDiscount(
        charge=charge,
        kind=kind,
        value=value,
        amount=amount.quantize(Decimal("0.0001")),
        reason=reason,
        authorized_by=actor,
    )
    discount.full_clean()
    discount.save()
    _sync_draft_total(booking)
    return discount


@transaction.atomic
def remove_draft_item(*, booking_id, agency, model, item_id, relation):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    if booking.status != Booking.Status.DRAFT:
        raise ValidationError("Draft details cannot change after confirmation.")
    item = model.objects.get(pk=item_id, **{relation: booking})
    item.delete()
    _sync_draft_total(booking)


@transaction.atomic
def confirm_booking_draft(*, booking_id, agency):
    booking = (
        Booking.objects.select_for_update()
        .select_related("agency", "branch", "customer", "trip", "currency", "accounting_currency")
        .get(pk=booking_id, agency=agency)
    )
    if booking.status != Booking.Status.DRAFT:
        raise ValidationError("Only draft bookings can be confirmed.")
    travelers = list(booking.travelers.select_related("traveler", "passenger_category"))
    if not travelers:
        raise ValidationError("Add at least one traveler before confirmation.")
    if len(travelers) != booking.expected_travelers:
        raise ValidationError(f"Validate all {booking.expected_travelers} travelers before confirmation; {len(travelers)} added.")
    from trips.models import Trip
    from .readiness import booking_capacity, traveler_issues

    booking.trip = Trip.objects.select_for_update().get(pk=booking.trip_id)
    if not booking_capacity(booking)["has_capacity"]:
        raise ValidationError("The trip does not have enough remaining places for this booking.")
    if booking.commercial_details.get('payment_plan'):
        from .readiness import booking_readiness
        if not booking_readiness(booking)['is_ready']:
            raise ValidationError('Complete valid passports and required room assignments before confirming the client agreement.')
    if not (booking.customer.phone.strip() or booking.customer.email.strip()):
        raise ValidationError("Add a phone number or email for the booking customer.")
    from reference.models import PassengerCategory

    for traveler_link in travelers:
        passport = traveler_link.traveler.passports.filter(status="CURRENT").first()
        birth_date = passport.birth_date if passport else traveler_link.traveler.birth_date
        if birth_date is None:
            continue
        category_code = passenger_category_code(birth_date, booking.trip.return_date)
        passenger_category = PassengerCategory.objects.get(
            code__iexact=category_code, is_system=True, is_active=True
        )
        if traveler_link.passenger_category_id != passenger_category.id:
            traveler_link.passenger_category = passenger_category
            traveler_link.save(update_fields=["passenger_category"])
    from finance.airline_rules import validate_airline_booking
    validate_airline_booking(booking)
    charges = list(
        BookingTravelerCharge.objects.filter(booking_traveler__booking=booking)
        .select_related(
            "booking_traveler__traveler",
            "booking_traveler__passenger_category",
            "source_price__trip_hotel__hotel",
            "source_price__room_type",
            "source_price__passenger_category",
            "source_price__currency",
        )
        .prefetch_related("discounts")
    )
    charged_ids = {item.booking_traveler_id for item in charges}
    if any(item.id not in charged_ids for item in travelers):
        raise ValidationError("Every traveler requires at least one price charge.")
    category_mismatches = []
    for charge in charges:
        if (
            charge.source_price_id
            and charge.source_price.passenger_category_id
            != charge.booking_traveler.passenger_category_id
            and not (charge.pricing_snapshot.get('passenger_category') == 'CHD' and charge.source_price.passenger_category.code.upper() == 'ADT')
        ):
            selected_price = charge.source_price
            required_category = charge.booking_traveler.passenger_category
            matching_price_exists = TripHotelPrice.objects.filter(
                trip_hotel_id=selected_price.trip_hotel_id,
                room_type_id=selected_price.room_type_id,
                passenger_category_id=required_category.id,
                bed_basis=selected_price.bed_basis,
                currency_id=selected_price.currency_id,
            ).exists()
            next_step = (
                f"Select the available {required_category.code.upper()} price."
                if matching_price_exists
                else f"No matching {required_category.code.upper()} price is configured; "
                "create one first or replace this line with a custom price."
            )
            category_mismatches.append(
                "Hotel price category mismatch for "
                f"{charge.booking_traveler.traveler.display_name}: traveler category is "
                f"{required_category.code.upper()} ({required_category.name}) on return date "
                f"{booking.trip.return_date}, but the selected price is "
                f"{selected_price.passenger_category.code.upper()} "
                f"({selected_price.passenger_category.name}) for hotel "
                f"{selected_price.trip_hotel.hotel.name}, room type "
                f"{selected_price.room_type.name}, amount {selected_price.amount} "
                f"{selected_price.currency_id}. {next_step}"
            )
    if category_mismatches:
        raise ValidationError(category_mismatches)
    for link in travelers:
        issues = traveler_issues(link)
        if issues:
            raise ValidationError(f"{link.traveler}: {'; '.join(issues)}")

    from .commercial import extra_total, validate_payment_plan
    total = sum((item.final_amount for item in charges), Decimal("0")) + extra_total(booking)
    validate_payment_plan(booking, total)
    booking.total_amount = total.quantize(Decimal("0.0001"))
    rate = booking.accounting_exchange_rate
    booking.accounting_total_amount = (booking.total_amount * rate).quantize(Decimal("0.0001"))
    booking.status = Booking.Status.CONFIRMED
    booking.save()
    accommodations = []
    for charge in charges:
        price = charge.source_price
        if not price:
            continue
        accommodation = BookingAccommodation.objects.create(
            booking=booking,
            trip_hotel=price.trip_hotel,
            room_type=price.room_type,
            passenger_category=charge.booking_traveler.passenger_category,
            bed_basis=price.bed_basis,
            quantity=1,
            unit_amount=charge.final_amount,
            total_amount=charge.final_amount,
            currency=booking.currency,
        )
        accommodations.append(accommodation)
    flights = [
        BookingFlight.objects.create(booking=booking, trip_flight=flight)
        for flight in booking.trip.flights.order_by("order")
    ]
    payload = _snapshot_payload(booking, None, accommodations, flights)
    payload["source"] = "DIRECT"
    payload["travelers"] = []
    payload["commercial_details"] = booking.commercial_details
    payload["partner"] = {"id": str(booking.partner_id), "name": booking.partner.name} if booking.partner_id else None
    payload["assigned_rooms"] = [{"traveler": str(a.booking_traveler_id), "hotel": a.room.trip_hotel.hotel.name, "room_type": a.room.room_type.name, "room": a.room.label} for link in travelers for a in link.trip_room_assignments.select_related("room__trip_hotel__hotel", "room__room_type")]
    for item in travelers:
        passport = item.traveler.passports.filter(status="CURRENT").first()
        validity = (
            passport_validity(passport.expiry_date, booking.trip.return_date)
            if passport
            else passport_validity(None, booking.trip.return_date)
        )
        birth_date = passport.birth_date if passport else item.traveler.birth_date
        payload["travelers"].append(
            {
                "id": str(item.id),
                "traveler_id": str(item.traveler_id),
                "name": item.traveler.display_name,
                "birth_date": birth_date.isoformat() if birth_date else None,
                "gender": item.traveler.gender,
                "passenger_category": item.passenger_category.name,
                "passenger_category_code": item.passenger_category.code,
                "seat_required": item.seat_required,
                "service_type": item.service_type,
                "category_reference_date": booking.trip.return_date.isoformat(),
                "is_customer_contact": item.is_customer_contact,
                "passport": (
                    {
                        "number": passport.passport_number,
                        "nationality": str(passport.nationality_id),
                        "issue_date": passport.issue_date.isoformat(),
                        "expiry_date": passport.expiry_date.isoformat(),
                        "required_valid_until": validity.required_until.isoformat(),
                        "validity_status": validity.status,
                        "is_valid": validity.is_valid,
                    }
                    if passport
                    else None
                ),
            }
        )
    payload["charges"] = [
        {
            "id": str(item.id),
            "traveler_id": str(item.booking_traveler_id),
            "description": item.description,
            "base_amount": str(item.base_amount),
            "discount_amount": str(item.discount_amount),
            "final_amount": str(item.final_amount),
        }
        for item in charges
    ]
    payload["rooms"] = [
        {
            "id": str(room.pk),
            "trip_hotel_id": str(room.trip_hotel_id),
            "hotel": room.trip_hotel.hotel.name,
            "room_type": room.room_type.name,
            "label": room.label,
            "capacity": room.capacity,
            "traveler_ids": [
                str(link.booking_traveler_id) for link in room.traveler_assignments.all()
            ],
        }
        for room in booking.room_groups.select_related(
            "trip_hotel__hotel", "room_type"
        ).prefetch_related("traveler_assignments")
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    BookingSnapshot.objects.create(
        booking=booking,
        payload=payload,
        sha256=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )
    return booking


@transaction.atomic
def add_booking_traveler(
    *,
    booking_id,
    agency,
    traveler,
    passenger_category,
    bed_requirement,
    notes="",
    is_customer_contact=False,
):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    if booking.status not in {Booking.Status.DRAFT, Booking.Status.CONFIRMED}:
        raise ValidationError("Travelers cannot be changed in this booking state.")
    if booking.travelers.count() >= booking.expected_travelers:
        raise ValidationError("The requested traveler count is already reached. Update the draft booking size first.")
    if booking.status == Booking.Status.CONFIRMED:
        from trips.models import Trip
        from .readiness import booking_capacity

        booking.trip = Trip.objects.select_for_update().get(pk=booking.trip_id)
        if not booking_capacity(booking)["has_capacity"]:
            raise ValidationError("The trip does not have enough remaining places.")
    link = BookingTraveler(
        booking=booking,
        traveler=traveler,
        passenger_category=passenger_category,
        bed_requirement=bed_requirement,
        notes=notes,
        is_customer_contact=is_customer_contact,
    )
    link.full_clean()
    link.save()
    if booking.status == Booking.Status.CONFIRMED:
        from finance.airline_rules import validate_airline_booking
        validate_airline_booking(booking)
    return link


@transaction.atomic
def remove_booking_traveler(*, booking_id, link_id, agency):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    if booking.status not in {Booking.Status.DRAFT, Booking.Status.CONFIRMED}:
        raise ValidationError("Travelers cannot be changed in this booking state.")
    if booking.status == Booking.Status.CONFIRMED:
        raise ValidationError("A confirmed booking must retain its validated travelers.")
    BookingTraveler.objects.get(pk=link_id, booking=booking).delete()


@transaction.atomic
def transition_booking(*, booking_id, agency, target_status, cancellation_reason=""):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    if booking.status != Booking.Status.CONFIRMED or target_status not in {
        Booking.Status.CANCELLED,
        Booking.Status.COMPLETED,
    }:
        raise ValidationError(
            f"Booking cannot transition from {booking.status} to {target_status}."
        )
    if target_status == Booking.Status.CANCELLED and not cancellation_reason.strip():
        raise ValidationError("A cancellation reason is required.")
    if target_status == Booking.Status.COMPLETED and not booking.travelers.exists():
        raise ValidationError("A booking requires at least one traveler before completion.")
    booking.status = target_status
    fields = ["status", "updated_at"]
    if target_status == Booking.Status.CANCELLED:
        from trips.models import TripRoomAssignment

        TripRoomAssignment.objects.filter(
            booking_traveler__booking=booking
        ).delete()
        BookingRoomTraveler.objects.filter(
            booking_traveler__booking=booking
        ).delete()
        booking.cancellation_reason = cancellation_reason.strip()
        booking.cancelled_at = timezone.now()
        fields.extend(["cancellation_reason", "cancelled_at"])
    else:
        booking.completed_at = timezone.now()
        fields.append("completed_at")
    booking.save(update_fields=fields)
    return booking


@transaction.atomic
def update_booking_size(*, booking_id, agency, expected_travelers):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    if booking.status != Booking.Status.DRAFT:
        raise ValidationError("Booking size can only change while the booking is a draft.")
    if expected_travelers < 1 or expected_travelers < booking.travelers.count():
        raise ValidationError("Booking size must be at least the number of travelers already added.")
    booking.expected_travelers = expected_travelers
    booking.full_clean()
    booking.save(update_fields=["expected_travelers", "updated_at"])
    return booking


def _set_sold_group_size(booking, accommodations):
    counts = {}
    for item in accommodations:
        stop = item.trip_hotel.stop_id
        counts[stop] = counts.get(stop, 0) + item.quantity
    booking.expected_travelers = max(counts.values(), default=1)
    booking.save(update_fields=["expected_travelers"])
