"""Validate airline commitments when confirming or changing passengers."""

from django.core.exceptions import ValidationError

from finance.models import AirlinePricing


def validate_airline_booking(booking):
    pricing = AirlinePricing.objects.filter(trip_id=booking.trip_id).first()
    own = list(
        booking.travelers.exclude(service_type="VISA_ONLY").select_related("passenger_category")
    )
    if any(link.passenger_category.code.upper() == "INF" and link.seat_required for link in own):
        fare = (
            next((row.get("price") for row in pricing.rows if row["category"] == "INF_SEAT"), None)
            if pricing
            else None
        )
        if fare is None:
            raise ValidationError(
                "Enter the infant with seat fare in Money Flow / Airline pricings "
                "before confirming this passenger."
            )
    if pricing:
        fares = {row["category"]: row.get("price") for row in pricing.rows}
        for link in own:
            code = link.passenger_category.code.upper()
            if code != "INF" and link.seat_required is False:
                continue
            category = (
                "ADULT"
                if code == "ADT"
                else "INF_SEAT"
                if code == "INF" and link.seat_required
                else code
            )
            if fares.get(category) is None:
                raise ValidationError(
                    f"Enter the airline fare for {category} in Money Flow "
                    "before confirming this passenger."
                )
    if pricing and booking.trip.max_travelers is not None:
        from bookings.models import BookingTraveler
        from bookings.readiness import consumes_seat

        links = (
            BookingTraveler.objects.filter(
                booking__trip_id=booking.trip_id, booking__status__in=["CONFIRMED", "COMPLETED"]
            )
            .exclude(booking_id=booking.pk)
            .exclude(service_type="VISA_ONLY")
            .select_related("passenger_category")
        )
        occupied = sum(consumes_seat(link) for link in [*links, *own])
        reserved = sum(
            row["seats"]
            for row in pricing.rows
            if row["category"] in {"FREE", "DISCOUNT_50", "DISCOUNT_60", "DISCOUNT_100"}
        )
        if occupied + reserved > booking.trip.max_travelers:
            raise ValidationError(
                "Passengers and reserved airline tickets exceed trip seat capacity."
            )
