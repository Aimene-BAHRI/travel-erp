from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from bookings.models import Booking, BookingTraveler
from bookings.readiness import consumes_seat
from bookings.services import confirm_booking_draft
from finance.airline_rules import validate_airline_booking
from finance.models import AirlinePricing
from reference.models import PassengerCategory
from tests.test_airline_finance import defaults
from tests.test_bookings import booking_data as source_booking_data
from tests.test_bookings import client_for, create_booking


@pytest.fixture
def booking_data(db):
    return source_booking_data.__wrapped__(db)


def setup(data, capacity=10):
    trip = data["trip"]
    trip.max_travelers = capacity
    trip.save()
    rows = defaults()["rows"]
    for row in rows:
        row["seats"] = 0
        row["price"] = {"ADULT": "100000", "CHD": "80000", "INF": "10000", "INF_SEAT": "60000"}.get(
            row["category"], "0"
        )
    pricing = AirlinePricing.objects.create(trip=trip, rows=rows)
    booking = create_booking(data)
    link = BookingTraveler.objects.create(
        booking=booking,
        traveler=data["traveler"],
        passenger_category=data["adult"],
        bed_requirement="REQUIRED",
    )
    return pricing, booking, link


def test_estimate_replaces_only_confirmed_seats_and_restores_on_cancellation(booking_data):
    pricing, booking, link = setup(booking_data)
    assert pricing.total == Decimal("1000000")
    link.passenger_category = PassengerCategory.objects.get(code__iexact="CHD", is_system=True)
    link.save()
    assert pricing.total == Decimal("980000")
    assert pricing.unbooked_seats == 9
    booking.status = Booking.Status.DRAFT
    booking.save()
    assert pricing.total == Decimal("1000000")
    booking.status = Booking.Status.COMPLETED
    booking.save()
    assert pricing.total == Decimal("980000")
    booking.status = Booking.Status.CANCELLED
    booking.save()
    assert pricing.total == Decimal("1000000")


def test_infant_seat_selection_uses_separate_fare_and_capacity(booking_data):
    pricing, booking, link = setup(booking_data)
    link.passenger_category = PassengerCategory.objects.get(code__iexact="INF", is_system=True)
    link.save()
    assert not consumes_seat(link)
    assert pricing.total == Decimal("1010000")
    assert pricing.unbooked_seats == 10
    link.seat_required = True
    link.save()
    assert consumes_seat(link)
    assert pricing.total == Decimal("960000")
    assert pricing.unbooked_seats == 9
    link.service_type = "VISA_ONLY"
    link.save()
    assert not consumes_seat(link)
    assert pricing.total == Decimal("1000000")


def test_missing_seated_infant_fare_blocks_confirmation(booking_data):
    pricing, booking, link = setup(booking_data)
    pricing.rows = [row for row in pricing.rows if row["category"] != "INF_SEAT"]
    pricing.save()
    link.passenger_category = PassengerCategory.objects.get(code__iexact="INF", is_system=True)
    link.seat_required = True
    link.save()
    booking.status = Booking.Status.DRAFT
    booking.expected_travelers = 1
    booking.save()
    with pytest.raises(ValidationError, match="infant with seat fare"):
        confirm_booking_draft(booking_id=booking.pk, agency=booking.agency)
    booking.refresh_from_db()
    assert booking.status == Booking.Status.DRAFT


def test_reservations_cannot_double_book_capacity(booking_data):
    pricing, booking, link = setup(booking_data, capacity=1)
    for row in pricing.rows:
        if row["category"] == "FREE":
            row["seats"] = 1
    pricing.save()
    with pytest.raises(ValidationError, match="seat capacity"):
        validate_airline_booking(booking)


def test_api_initial_estimate_installments_and_missing_fare_validation(booking_data):
    pricing, booking, link = setup(booking_data)
    client = client_for(booking_data["owner"])
    url = f"/api/v1/finance/airlines/{booking.trip_id}/"
    result = client.get(url)
    assert Decimal(result.data["total"]) == 1000000
    assert result.data["unbooked_seats"] == 9
    response = client.post(
        url + "schedule-installment/",
        {
            "amount": "1000000",
            "due_date": "2027-01-01",
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert Decimal(response.data["remaining"]) == 1000000
    assert Decimal(response.data["scheduled"]) == 1000000
    payload = {"rows": result.data["rows"], "visa_price": "0"}
    infant_row = next(row for row in payload["rows"] if row["category"] == "INF_SEAT")
    infant_row["price"] = None
    assert client.put(url, payload, format="json").status_code == 200
    link.passenger_category = PassengerCategory.objects.get(code__iexact="INF", is_system=True)
    link.seat_required = True
    link.save()
    assert client.put(url, payload, format="json").status_code == 400
    broken = client.get(url)
    assert broken.status_code == 200
    assert broken.data["total"] is None
    assert broken.data["pricing_error"]
    assert (
        client.post(
            url + "schedule-installment/",
            {
                "amount": "1",
                "due_date": "2027-01-01",
            },
            format="json",
        ).status_code
        == 400
    )
    infant_row["price"] = "60000"
    assert client.put(url, payload, format="json").status_code == 200
    assert Decimal(client.get(url).data["total"]) == 960000


@pytest.mark.parametrize("capacity,missing_fare", [(1, False), (10, True)])
def test_confirmed_traveler_flow_rejects_invalid_seated_infant_atomically(
    booking_data, capacity, missing_fare
):
    pricing, booking, link = setup(booking_data, capacity=capacity)
    if missing_fare:
        for row in pricing.rows:
            if row["category"] == "INF_SEAT":
                row["price"] = None
        pricing.save()
    client = client_for(booking_data["owner"])
    response = client.post(
        f"/api/v1/bookings/{booking.pk}/traveler-flow/",
        {
            "names_only": True,
            "first_name": "Baby",
            "last_name": "Passenger",
            "birth_date": "2026-01-01",
            "seat_required": True,
        },
        format="json",
    )
    assert response.status_code == 400, response.data
    assert booking.travelers.count() == 1
    if missing_fare:
        assert "infant with seat fare" in str(response.data)


def test_initial_pricing_without_bookings_uses_trip_capacity(booking_data):
    trip = booking_data["trip"]
    trip.max_travelers = 35
    trip.save()
    client = client_for(booking_data["owner"])
    url = f"/api/v1/finance/airlines/{trip.pk}/"
    initial = client.get(url).data
    assert initial["rows"][0]["seats"] == 35
    assert initial["unbooked_seats"] == 35
    initial["rows"][0]["price"] = "100000"
    saved = client.put(url, initial, format="json")
    assert saved.status_code == 200, saved.data
    assert Decimal(saved.data["total"]) == 3500000


def test_confirmed_infant_seat_selection_is_saved_and_priced(booking_data):
    pricing, booking, link = setup(booking_data)
    response = client_for(booking_data["owner"]).post(
        f"/api/v1/bookings/{booking.pk}/traveler-flow/",
        {
            "names_only": True,
            "first_name": "Baby",
            "last_name": "Passenger",
            "birth_date": "2026-01-01",
            "seat_required": True,
        },
        format="json",
    )
    assert response.status_code == 200, response.data
    infant = booking.travelers.exclude(pk=link.pk).get()
    assert infant.seat_required is True
    assert pricing.passenger_counts["INF_SEAT"] == 1
    assert pricing.unbooked_seats == 8
    assert pricing.total == Decimal("960000")


@pytest.mark.parametrize("category", ["CHD", "INF"])
def test_missing_child_or_infant_fare_is_not_treated_as_zero(booking_data, category):
    pricing, booking, link = setup(booking_data)
    for row in pricing.rows:
        if row["category"] == category:
            row["price"] = None
    pricing.save()
    link.passenger_category = PassengerCategory.objects.get(code__iexact=category, is_system=True)
    link.save()
    with pytest.raises(ValidationError, match=f"fare for {category}"):
        validate_airline_booking(booking)
    with pytest.raises(ValidationError, match="missing airline fares"):
        _ = pricing.total
