from datetime import UTC, date, datetime

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from bookings.models import Booking, BookingTraveler
from catalog.models import Airline, Hotel, RoomType, Supplier
from customers.models import Customer
from organizations.models import Agency, Branch
from reference.models import City, Country, Currency, PassengerCategory
from travelers.models import Traveler
from trips.models import Trip, TripClosingItem, TripHotel, TripRoomAssignment, TripStop


@pytest.fixture
def trip_data(db):
    algeria = Country.objects.create(name="Algeria", code="DZ")
    saudi = Country.objects.create(name="Saudi Arabia", code="SA")
    oran = City.objects.create(country=algeria, name="Oran")
    medina = City.objects.create(country=saudi, name="Medina")
    mecca = City.objects.create(country=saudi, name="Mecca")
    first = Agency.objects.create(name="First Travel", slug="trip-first")
    second = Agency.objects.create(name="Second Travel", slug="trip-second")
    first_branch = Branch.objects.create(agency=first, name="Oran", code="ORN")
    second_branch = Branch.objects.create(agency=second, name="Algiers", code="ALG")
    owner = User.objects.create_user(
        email="trip-owner@first.test",
        password="safe-test-password",
        agency=first,
        is_superuser=True,
    )
    foreign_owner = User.objects.create_user(
        email="trip-owner@second.test",
        password="safe-test-password",
        agency=second,
        is_superuser=True,
    )
    trip = Trip.objects.create(
        agency=first,
        branch=first_branch,
        code="umrah-2027-01",
        name="Umrah January 2027",
        departure_date=date(2027, 1, 10),
        return_date=date(2027, 1, 20),
        created_by=owner,
    )
    return {
        "algeria": algeria,
        "saudi": saudi,
        "oran": oran,
        "medina": medina,
        "mecca": mecca,
        "first": first,
        "second": second,
        "first_branch": first_branch,
        "second_branch": second_branch,
        "owner": owner,
        "foreign_owner": foreign_owner,
        "trip": trip,
    }


def authenticated_client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_trip_closing_is_gated_by_the_full_checklist(trip_data):
    trip = trip_data["trip"]
    trip.status = Trip.Status.COMPLETED
    trip.save(update_fields=["status"])
    client = authenticated_client(trip_data["owner"])

    summary = client.get(reverse("trip-closing", args=[trip.pk]))
    blocked = client.post(reverse("trip-close-closing", args=[trip.pk]), {}, format="json")

    assert summary.status_code == 200
    assert summary.data["status"] == Trip.ClosingStatus.PENDING
    assert summary.data["total_count"] == len(TripClosingItem.Key)
    assert blocked.status_code == 400

    for item in summary.data["items"]:
        completed = client.patch(
            reverse("trip-update-closing-item", args=[trip.pk, item["key"]]),
            {"state": TripClosingItem.State.COMPLETED, "notes": "Verified"},
            format="json",
        )
        assert completed.status_code == 200

    closed = client.post(reverse("trip-close-closing", args=[trip.pk]), {}, format="json")

    assert closed.status_code == 200
    assert closed.data["status"] == Trip.ClosingStatus.CLOSED
    assert closed.data["closed_by"] == trip_data["owner"].email


def test_closed_trip_closing_can_be_reopened(trip_data):
    trip = trip_data["trip"]
    trip.status = Trip.Status.COMPLETED
    trip.closing_status = Trip.ClosingStatus.CLOSED
    trip.closed_by = trip_data["owner"]
    trip.save(update_fields=["status", "closing_status", "closed_by"])

    response = authenticated_client(trip_data["owner"]).post(
        reverse("trip-reopen-closing", args=[trip.pk]), {}, format="json"
    )

    assert response.status_code == 200
    assert response.data["status"] == Trip.ClosingStatus.PENDING


def test_trip_cannot_open_without_an_itinerary(trip_data):
    response = authenticated_client(trip_data["owner"]).post(
        reverse("trip-transition", args=[trip_data["trip"].id]), {"status": "OPEN"}, format="json"
    )

    assert response.status_code == 400
    trip_data["trip"].refresh_from_db()
    assert trip_data["trip"].status == Trip.Status.DRAFT


def test_trip_opens_after_valid_itinerary_is_created(trip_data):
    client = authenticated_client(trip_data["owner"])
    stop_response = client.post(
        reverse("trip-stop-list"),
        {
            "trip": str(trip_data["trip"].id),
            "city": str(trip_data["medina"].id),
            "arrival_date": "2027-01-10",
            "departure_date": "2027-01-15",
            "order": 1,
        },
        format="json",
    )
    transition_response = client.post(
        reverse("trip-transition", args=[trip_data["trip"].id]), {"status": "OPEN"}, format="json"
    )

    assert stop_response.status_code == 201
    assert stop_response.data["nights"] == 5
    assert transition_response.status_code == 200
    assert transition_response.data["status"] == Trip.Status.OPEN


def test_overlapping_itinerary_stop_is_rejected_and_rolled_back(trip_data):
    TripStop.objects.create(
        trip=trip_data["trip"],
        city=trip_data["medina"],
        arrival_date=date(2027, 1, 10),
        departure_date=date(2027, 1, 15),
        order=1,
    )
    response = authenticated_client(trip_data["owner"]).post(
        reverse("trip-stop-list"),
        {
            "trip": str(trip_data["trip"].id),
            "city": str(trip_data["mecca"].id),
            "arrival_date": "2027-01-14",
            "departure_date": "2027-01-20",
            "order": 2,
        },
        format="json",
    )

    assert response.status_code == 400
    assert trip_data["trip"].stops.count() == 1


def test_nights_is_derived_not_stored(trip_data):
    stop = TripStop.objects.create(
        trip=trip_data["trip"],
        city=trip_data["medina"],
        arrival_date=date(2027, 1, 10),
        departure_date=date(2027, 1, 13),
        order=1,
    )

    assert stop.nights == 3
    assert "nights" not in {field.name for field in TripStop._meta.fields}


def test_trip_hotel_must_match_stop_city(trip_data):
    stop = TripStop.objects.create(
        trip=trip_data["trip"],
        city=trip_data["medina"],
        arrival_date=date(2027, 1, 10),
        departure_date=date(2027, 1, 15),
        order=1,
    )
    wrong_city_hotel = Hotel.objects.create(
        agency=trip_data["first"], city=trip_data["mecca"], name="Mecca Hotel"
    )

    response = authenticated_client(trip_data["owner"]).post(
        reverse("trip-hotel-list"),
        {"stop": str(stop.id), "hotel": str(wrong_city_hotel.id), "is_primary": True},
        format="json",
    )

    assert response.status_code == 400


def test_flight_arrival_must_follow_departure(trip_data):
    airline = Airline.objects.get(iata_code="AH")
    response = authenticated_client(trip_data["owner"]).post(
        reverse("trip-flight-list"),
        {
            "trip": str(trip_data["trip"].id),
            "airline": str(airline.id),
            "direction": "OUTBOUND",
            "flight_number": "AH100",
            "origin_city": str(trip_data["oran"].id),
            "destination_city": str(trip_data["medina"].id),
            "origin_airport_code": "ORN",
            "destination_airport_code": "MED",
            "departure_at": datetime(2027, 1, 10, 12, tzinfo=UTC).isoformat(),
            "arrival_at": datetime(2027, 1, 10, 10, tzinfo=UTC).isoformat(),
            "order": 1,
        },
        format="json",
    )

    assert response.status_code == 400


def test_ground_transport_connects_trip_cities(trip_data):
    supplier = Supplier.objects.create(agency=trip_data["first"], name="Saudi Coach")
    response = authenticated_client(trip_data["owner"]).post(
        reverse("trip-transport-list"),
        {
            "trip": str(trip_data["trip"].id),
            "mode": "BUS",
            "supplier": str(supplier.id),
            "origin_city": str(trip_data["mecca"].id),
            "destination_city": str(trip_data["medina"].id),
            "departure_at": datetime(2027, 1, 15, 8, tzinfo=UTC).isoformat(),
            "arrival_at": datetime(2027, 1, 15, 13, tzinfo=UTC).isoformat(),
            "reference": "BUS-15JAN",
            "order": 1,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["mode_display"] == "Bus"
    assert response.data["origin_city_name"] == "Mecca"
    assert response.data["destination_city_name"] == "Medina"


def test_ground_transport_rejects_foreign_supplier(trip_data):
    supplier = Supplier.objects.create(agency=trip_data["second"], name="Foreign Coach")
    response = authenticated_client(trip_data["owner"]).post(
        reverse("trip-transport-list"),
        {
            "trip": str(trip_data["trip"].id),
            "mode": "BUS",
            "supplier": str(supplier.id),
            "origin_city": str(trip_data["mecca"].id),
            "destination_city": str(trip_data["medina"].id),
            "departure_at": datetime(2027, 1, 15, 8, tzinfo=UTC).isoformat(),
            "arrival_at": datetime(2027, 1, 15, 13, tzinfo=UTC).isoformat(),
            "order": 1,
        },
        format="json",
    )

    assert response.status_code == 400


def test_trip_list_never_returns_foreign_agency(trip_data):
    foreign_trip = Trip.objects.create(
        agency=trip_data["second"],
        branch=trip_data["second_branch"],
        code="foreign-trip",
        name="Foreign Trip",
        departure_date=date(2027, 2, 1),
        return_date=date(2027, 2, 5),
        created_by=trip_data["foreign_owner"],
    )

    response = authenticated_client(trip_data["owner"]).get(reverse("trip-list"))

    ids = {str(item["id"]) for item in response.data["results"]}
    assert str(trip_data["trip"].id) in ids
    assert str(foreign_trip.id) not in ids


def test_trip_document_upload_uses_typed_owner(trip_data, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    uploaded = SimpleUploadedFile("program.pdf", b"trip-program", "application/pdf")

    response = authenticated_client(trip_data["owner"]).post(
        reverse("document-list"),
        {
            "file": uploaded,
            "category": "OTHER",
            "title": "Trip program",
            "owner_type": "TRIP",
            "owner_id": str(trip_data["trip"].id),
        },
        format="multipart",
    )

    assert response.status_code == 201
    assert response.data["owner_type"] == "TRIP"
    assert response.data["owner_id"] == str(trip_data["trip"].id)


def test_trip_accommodation_rooms_allocate_confirmed_travelers_by_stop(trip_data):
    stop = TripStop.objects.create(
        trip=trip_data["trip"],
        city=trip_data["medina"],
        arrival_date=date(2027, 1, 10),
        departure_date=date(2027, 1, 20),
        order=1,
    )
    hotel = Hotel.objects.create(
        agency=trip_data["first"], city=trip_data["medina"], name="Medina Allocation Hotel"
    )
    trip_hotel = TripHotel.objects.create(stop=stop, hotel=hotel, is_primary=True)
    room_type = RoomType.objects.create(
        agency=trip_data["first"], code="triple", name="Triple", default_standard_beds=3
    )
    customer = Customer.objects.create(
        agency=trip_data["first"],
        branch=trip_data["first_branch"],
        kind=Customer.Kind.INDIVIDUAL,
        first_name="Booking",
        last_name="Group",
        phone="0550000000",
        created_by=trip_data["owner"],
    )
    dzd = Currency.objects.get(code="DZD")
    booking = Booking.objects.create(
        agency=trip_data["first"],
        branch=trip_data["first_branch"],
        code="B-ROOMING-1",
        customer=customer,
        trip=trip_data["trip"],
        currency=dzd,
        total_amount=0,
        accounting_currency=dzd,
        accounting_total_amount=0,
        status=Booking.Status.CONFIRMED,
        created_by=trip_data["owner"],
    )
    adult = PassengerCategory.objects.get(code="adt", is_system=True)
    male = Traveler.objects.create(
        agency=trip_data["first"],
        branch=trip_data["first_branch"],
        first_name="Ali",
        last_name="Traveler",
        gender=Traveler.Gender.MALE,
        created_by=trip_data["owner"],
    )
    female = Traveler.objects.create(
        agency=trip_data["first"],
        branch=trip_data["first_branch"],
        first_name="Amina",
        last_name="Traveler",
        gender=Traveler.Gender.FEMALE,
        created_by=trip_data["owner"],
    )
    male_link = BookingTraveler.objects.create(
        booking=booking,
        traveler=male,
        passenger_category=adult,
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    female_link = BookingTraveler.objects.create(
        booking=booking,
        traveler=female,
        passenger_category=adult,
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    client = authenticated_client(trip_data["owner"])
    from bookings.models import BookingTravelerCharge
    from travelers.services import save_passport

    for link in [male_link, female_link]:
        save_passport(traveler=link.traveler, actor=trip_data["owner"], passport_number=f"ROOM{str(link.pk)[:8]}", first_name=link.traveler.first_name, last_name="Traveler", birth_date=date(1990, 1, 1), gender=link.traveler.gender, nationality=stop.city.country, issuing_country=stop.city.country, issue_date=date(2025, 1, 1), expiry_date=date(2035, 1, 1))
        BookingTravelerCharge.objects.create(booking_traveler=link, kind="SERVICE", description="Included package", base_amount=0, currency=dzd)

    room_response = client.post(
        reverse("trip-allocation-room-list"),
        {
            "trip_hotel": str(trip_hotel.pk),
            "room_type": str(room_type.pk),
            "label": "Room 01",
            "standard_beds": 1,
            "extra_beds": 0,
            "occupancy_policy": "ANY",
        },
        format="json",
    )

    first_assignment = client.post(
        reverse("trip-allocation-room-assign", args=[room_response.data["id"]]),
        {"booking_traveler": str(male_link.pk), "bed_number": 1},
        format="json",
    )
    full_room = client.post(
        reverse("trip-allocation-room-assign", args=[room_response.data["id"]]),
        {"booking_traveler": str(female_link.pk)},
        format="json",
    )
    expanded = client.patch(
        reverse("trip-allocation-room-detail", args=[room_response.data["id"]]),
        {"extra_beds": 1},
        format="json",
    )
    second_assignment = client.post(
        reverse("trip-allocation-room-assign", args=[room_response.data["id"]]),
        {"booking_traveler": str(female_link.pk), "bed_number": 2},
        format="json",
    )
    plan = client.get(reverse("trip-accommodation-plan", args=[trip_data["trip"].pk]))

    assert room_response.status_code == 201
    assert first_assignment.status_code == 201
    assert full_room.status_code == 400
    assert expanded.status_code == 200
    assert expanded.data["capacity"] == 2
    assert second_assignment.status_code == 201
    assert TripRoomAssignment.objects.filter(stop=stop).count() == 2
    assert plan.status_code == 200
    assert plan.data["summary"]["is_complete"] is True
    assert plan.data["stops"][0]["assigned_count"] == 2
