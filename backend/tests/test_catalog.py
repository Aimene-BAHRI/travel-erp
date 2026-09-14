import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Airline, Hotel, Room, RoomType, Supplier
from organizations.models import Agency
from reference.models import City, Country


@pytest.fixture
def catalog_data(db):
    country = Country.objects.create(name="Algeria", code="DZ")
    city = City.objects.create(country=country, name="Oran")
    first = Agency.objects.create(name="First Travel", slug="catalog-first")
    second = Agency.objects.create(name="Second Travel", slug="catalog-second")
    owner = User.objects.create_user(
        email="catalog-owner@first.test",
        password="safe-test-password",
        agency=first,
        is_superuser=True,
    )
    return country, city, first, second, owner


def test_airline_is_global_and_not_a_supplier(db):
    airline = Airline.objects.get(iata_code="AH")

    assert airline.name == "Air Algérie"
    assert not hasattr(airline, "agency")
    assert not hasattr(airline, "supplier")


def test_same_hotel_name_is_allowed_in_different_agencies(catalog_data):
    _, city, first, second, _ = catalog_data

    Hotel.objects.create(agency=first, city=city, name="Grand Hotel")
    Hotel.objects.create(agency=second, city=city, name="Grand Hotel")

    assert Hotel.objects.filter(name="Grand Hotel").count() == 2


def test_hotel_api_never_returns_foreign_agency(catalog_data):
    _, city, first, second, owner = catalog_data
    own_hotel = Hotel.objects.create(agency=first, city=city, name="Own Hotel")
    foreign_hotel = Hotel.objects.create(agency=second, city=city, name="Foreign Hotel")
    client = APIClient()
    client.force_authenticate(owner)

    response = client.get(reverse("hotel-list"))

    ids = {str(item["id"]) for item in response.data["results"]}
    assert str(own_hotel.id) in ids
    assert str(foreign_hotel.id) not in ids


def test_room_type_is_configurable_per_agency(catalog_data):
    _, _, first, _, owner = catalog_data
    client = APIClient()
    client.force_authenticate(owner)

    response = client.post(
        reverse("room-type-list"),
        {"code": "triple", "name": "Triple", "default_standard_beds": 3},
        format="json",
    )

    assert response.status_code == 201
    assert RoomType.objects.get(pk=response.data["id"]).agency == first


def test_room_rejects_room_type_from_another_agency(catalog_data):
    _, city, first, second, owner = catalog_data
    hotel = Hotel.objects.create(agency=first, city=city, name="Own Hotel")
    foreign_type = RoomType.objects.create(
        agency=second, code="foreign", name="Foreign", default_standard_beds=2
    )
    client = APIClient()
    client.force_authenticate(owner)

    response = client.post(
        reverse("room-list"),
        {
            "hotel": str(hotel.id),
            "room_type": str(foreign_type.id),
            "number": "301",
            "standard_beds": 3,
            "max_extra_beds": 1,
        },
        format="json",
    )

    assert response.status_code == 400


def test_room_keeps_commercial_type_separate_from_physical_capacity(catalog_data):
    _, city, first, _, _ = catalog_data
    hotel = Hotel.objects.create(agency=first, city=city, name="Own Hotel")
    room_type = RoomType.objects.create(
        agency=first, code="triple", name="Triple", default_standard_beds=3
    )
    room = Room(
        agency=first,
        hotel=hotel,
        room_type=room_type,
        number="301",
        standard_beds=3,
        max_extra_beds=1,
    )
    room.full_clean()
    room.save()

    assert room.room_type.name == "Triple"
    assert room.maximum_beds == 4
    assert room.standard_beds == 3


def test_supplier_is_agency_owned(catalog_data):
    _, _, first, second, _ = catalog_data
    Supplier.objects.create(agency=first, name="Shared Name")
    Supplier.objects.create(agency=second, name="Shared Name")

    assert Supplier.objects.filter(name="Shared Name").count() == 2


def test_room_model_rejects_cross_agency_hotel(catalog_data):
    _, city, first, second, _ = catalog_data
    foreign_hotel = Hotel.objects.create(agency=second, city=city, name="Foreign")
    room_type = RoomType.objects.create(
        agency=first, code="double", name="Double", default_standard_beds=2
    )
    room = Room(
        agency=first,
        hotel=foreign_hotel,
        room_type=room_type,
        number="100",
        standard_beds=2,
    )

    with pytest.raises(ValidationError):
        room.full_clean()
