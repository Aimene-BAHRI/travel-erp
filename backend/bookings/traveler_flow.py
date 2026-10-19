from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from audit.services import record_event
from reference.models import PassengerCategory
from travelers.api.serializers import PassportSerializer
from travelers.models import Traveler
from travelers.rules import passenger_category_code
from trips.models import Trip, TripAllocationRoom
from trips.services import assign_traveler_to_room

from .models import Booking, BookingTraveler, BookingTravelerCharge, BookingDiscount
from .readiness import booking_capacity, require_room_ready
from .services import _sync_draft_total


class TravelerFlowInput(serializers.Serializer):
    link_id = serializers.UUIDField(required=False, allow_null=True)
    names_only = serializers.BooleanField(default=False)
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    birth_date = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=["M", "F", "X"], default="X")
    passport = serializers.DictField(required=False)
    price_mode = serializers.ChoiceField(
        choices=["INCLUDED", "ADDITIONAL", "EXISTING", "REPLACE_DRAFT"], default="INCLUDED"
    )
    amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal("0"), required=False
    )
    source_price = serializers.UUIDField(required=False, allow_null=True)
    use_trip_price = serializers.BooleanField(default=False)
    bed_requirement = serializers.ChoiceField(choices=["REQUIRED", "NOT_REQUIRED"], required=False)
    seat_required = serializers.BooleanField(required=False, allow_null=True)
    service_type = serializers.ChoiceField(choices=["PACK", "VISA_ONLY", "TICKET_ONLY", "CUSTOM"], required=False)
    included_stops = serializers.ListField(child=serializers.UUIDField(), required=False)
    rooms = serializers.ListField(child=serializers.UUIDField(), default=list)
    photo = serializers.DictField(required=False)
    passport_scan = serializers.DictField(required=False)


@transaction.atomic
def save_traveler_flow(*, booking_id, agency, request, data):
    booking = Booking.objects.select_for_update().get(pk=booking_id, agency=agency)
    if booking.status not in {Booking.Status.DRAFT, Booking.Status.CONFIRMED}:
        raise ValidationError("This booking cannot be changed.")
    booking.trip = Trip.objects.select_for_update().get(pk=booking.trip_id)
    link_id = data.get("link_id")
    link = (
        booking.travelers.select_related("traveler").filter(pk=link_id).first() if link_id else None
    )
    if link_id and link is None:
        raise ValidationError("Traveler does not belong to this booking.")
    if not link and booking.travelers.count() >= booking.expected_travelers:
        raise ValidationError("All requested travelers have already been added.")
    birth = data.get("birth_date")
    if birth and birth > timezone.localdate():
        raise ValidationError("Birth date cannot be in the future.")
    if not data["names_only"] and (not data["last_name"] or not birth):
        raise ValidationError("First name, last name, and birth date are required.")
    if link and data["names_only"]:
        raise ValidationError("Use Complete details to update an existing traveler.")
    person = (
        link.traveler
        if link
        else Traveler(agency=agency, branch=booking.branch, created_by=request.user)
    )
    person.first_name = data["first_name"]
    person.last_name = data["last_name"]
    person.birth_date = birth
    person.gender = data["gender"]
    person.full_clean()
    person.save()
    category = PassengerCategory.objects.get(
        code__iexact=passenger_category_code(birth, booking.trip.return_date) if birth else "ADT",
        is_system=True,
        is_active=True,
    )
    if link is None:
        link = BookingTraveler(booking=booking, traveler=person)
    link.passenger_category = category
    link.service_type = data.get("service_type", link.service_type)
    link.seat_required = data.get("seat_required", link.seat_required)
    link.bed_requirement = "NOT_REQUIRED" if category.code.upper() == "INF" else data.get("bed_requirement", link.bed_requirement or "REQUIRED")
    link.full_clean()
    link.save()
    if not booking_capacity(booking)["has_capacity"]:
        raise ValidationError("The trip does not have enough remaining places.")
    if "included_stops" in data:
        stops = list(booking.trip.stops.filter(pk__in=data["included_stops"]))
        if len(stops) != len(data["included_stops"]):
            raise ValidationError("Selected service stays must belong to this trip.")
        link.included_stops.set(stops)
    if data["names_only"]:
        if data.get("passport_scan"):
            raise serializers.ValidationError({"passport_scan": "Complete passport details to save the full passport image."})
        if booking.status == Booking.Status.CONFIRMED:
            from finance.airline_rules import validate_airline_booking
            validate_airline_booking(booking)
        from .passport_photo import save_cropped_photo
        save_cropped_photo(person, data.get("photo"), request)
        record_event(
            actor=request.user,
            action="booking.traveler_names_saved",
            target_type="bookings.Booking",
            target_id=str(booking.pk),
            metadata={"traveler": str(link.pk)},
        )
        return booking
    passport_data = data.get("passport")
    if not passport_data:
        raise ValidationError("Enter or scan a passport before validating this traveler.")
    passport_data = {**passport_data, "traveler": str(person.pk), "status": "CURRENT"}
    if passport_data.get("birth_country") == "":
        passport_data["birth_country"] = None
    current = person.passports.filter(status="CURRENT").first()
    passport = PassportSerializer(
        instance=current, data=passport_data, context={"request": request}
    )
    passport.is_valid(raise_exception=True)
    passport.save()
    person.refresh_from_db()
    link.passenger_category = PassengerCategory.objects.get(
        code__iexact=passenger_category_code(person.birth_date, booking.trip.return_date),
        is_system=True,
        is_active=True,
    )
    link.bed_requirement = "NOT_REQUIRED" if link.passenger_category.code.upper() == "INF" else data.get("bed_requirement", link.bed_requirement)
    link.save(update_fields=["passenger_category", "bed_requirement"])
    if not booking_capacity(booking)["has_capacity"]:
        raise ValidationError("The trip does not have enough remaining places.")
    if booking.status == Booking.Status.CONFIRMED:
        from finance.airline_rules import validate_airline_booking
        validate_airline_booking(booking)
    resolved = None
    price = None
    if data["price_mode"] == "REPLACE_DRAFT":
        if booking.status != Booking.Status.DRAFT or booking.financial_transactions.exists():
            raise ValidationError("Only an unpaid draft can have its traveler price replaced.")
        link.charges.all().delete()
        data["price_mode"] = "INCLUDED"
    if data.get("use_trip_price") and not link.charges.exists():
        from pricing.models import TripHotelPrice
        from pricing.services import resolve_traveler_price
        if data.get("source_price"):
            price = TripHotelPrice.objects.select_related("trip_hotel__stop", "room_type", "passenger_category").filter(pk=data["source_price"], agency=agency, scope="TRIP_PACKAGE").first()
            if price is None:
                raise ValidationError("Select a whole-trip hotel package price.")
        resolved = resolve_traveler_price(trip=booking.trip, trip_hotel=price.trip_hotel if price else None, room_type=price.room_type if price else None, passenger_category=link.passenger_category, bed_requirement=link.bed_requirement)
        if resolved.currency_id != booking.currency_id:
            raise ValidationError("Resolved price currency must match booking currency.")
        data["amount"] = resolved.amount
    mode = data["price_mode"]
    existing = link.charges.exists()
    if mode == "EXISTING":
        if not existing:
            raise ValidationError("This traveler has no existing individual price.")
    else:
        if existing:
            raise ValidationError(
                "This traveler already has an individual price. Keep the existing price."
            )
        if "amount" not in data:
            raise ValidationError("Enter the individual price.")
        amount = data["amount"]
        allocated = sum(
            (
                c.final_amount
                for c in BookingTravelerCharge.objects.filter(
                    booking_traveler__booking=booking
                ).prefetch_related("discounts")
            ),
            Decimal("0"),
        )
        if (
            booking.status == Booking.Status.CONFIRMED
            and mode == "INCLUDED"
            and allocated + amount > booking.total_amount
        ):
            raise ValidationError(
                "Included individual prices exceed the confirmed total. "
                "Review existing prices before allocating more of that total."
            )
        charge = BookingTravelerCharge.objects.create(
            booking_traveler=link,
            kind="SERVICE",
            description="Individual package price",
            base_amount=resolved.base_amount if resolved else amount,
            source_price_id=resolved.source_price_id if resolved else None,
            pricing_snapshot=({"base_amount": str(resolved.base_amount), "discount_amount": str(resolved.discount_amount), "agreed_amount": str(resolved.amount), "passenger_category": resolved.passenger_category, "bed_basis": resolved.bed_basis, "currency": resolved.currency_id, "trip_hotel": str(price.trip_hotel_id) if price else None, "room_type": str(price.room_type_id) if price else None} if resolved else {}),
            currency=booking.currency,
            notes=f"Traveler completion: {mode}",
        )
        if resolved and resolved.discount_amount:
            BookingDiscount.objects.create(charge=charge, kind="AMOUNT", value=resolved.discount_amount, amount=resolved.discount_amount, reason="Configured child-with-bed discount", authorized_by=request.user)
        if booking.status == Booking.Status.DRAFT:
            _sync_draft_total(booking)
        elif mode == "ADDITIONAL":
            previous = booking.total_amount
            total = previous + amount
            # Explicit, audited supplement; the original confirmation snapshot remains immutable.
            Booking.objects.filter(pk=booking.pk).update(
                total_amount=total,
                accounting_total_amount=(total * booking.accounting_exchange_rate).quantize(
                    Decimal("0.0001")
                ),
                updated_at=timezone.now(),
            )
            record_event(
                actor=request.user,
                action="booking.price_supplement_added",
                target_type="bookings.Booking",
                target_id=str(booking.pk),
                metadata={
                    "charge": str(charge.pk),
                    "previous_total": str(previous),
                    "new_total": str(total),
                    "amount": str(amount),
                    "currency": str(booking.currency_id),
                },
            )
    from .readiness import consumes_bed, required_stops, passport_issues, traveler_issues
    issues = traveler_issues(link) + passport_issues(link)
    if issues:
        raise ValidationError(issues)
    room_ids = data["rooms"]
    rooms = list(
        TripAllocationRoom.objects.filter(
            pk__in=room_ids, trip_hotel__stop__trip=booking.trip
        ).select_related("trip_hotel__stop")
    )
    if len(rooms) != len(room_ids):
        raise ValidationError("One or more selected rooms are unavailable.")
    required = {stop.pk for stop in required_stops(link, list(booking.trip.stops.filter(hotels__isnull=False).distinct()))}
    selected = [room.trip_hotel.stop_id for room in rooms]
    if set(selected) != required or len(selected) != len(set(selected)):
        raise ValidationError("Select one room for each hotel stay.")
    for room in sorted(rooms, key=lambda item: str(item.pk)):
        assign_traveler_to_room(
            room_id=room.pk, booking_traveler=link, agency=agency, actor=request.user
        )
    if booking.status == Booking.Status.DRAFT:
        link.trip_room_assignments.exclude(stop_id__in=required).delete()
    record_event(
        actor=request.user,
        action="booking.traveler_completed",
        target_type="bookings.Booking",
        target_id=str(booking.pk),
        metadata={
            "traveler": str(link.pk),
            "price_mode": mode,
            "rooms": [str(pk) for pk in room_ids],
        },
    )
    booking.refresh_from_db()
    from .passport_photo import save_cropped_photo
    save_cropped_photo(person, data.get("photo"), request)
    from .passport_photo import save_passport_image
    save_passport_image(passport.instance, data.get("passport_scan"), request)
    return booking
