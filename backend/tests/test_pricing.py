from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from catalog.models import Hotel, RoomType
from customers.models import Customer
from organizations.models import Agency, Branch
from pricing.models import Quote, QuoteLine, SeasonalFlightPrice, TripHotelPrice
from pricing.services import (
    add_price_to_quote,
    issue_quote,
    quantize_money,
    resolve_traveler_price,
)
from reference.models import AgencyCurrency, City, Country, Currency, PassengerCategory
from trips.models import Trip, TripHotel, TripStop


@pytest.fixture
def pricing_data(db):
    country = Country.objects.create(name="Pricing Country", code="PC")
    city = City.objects.create(country=country, name="Pricing City")
    agency = Agency.objects.create(name="Pricing Travel", slug="pricing-travel")
    foreign_agency = Agency.objects.create(name="Foreign Pricing", slug="foreign-pricing")
    branch = Branch.objects.create(agency=agency, name="Main", code="MAIN")
    foreign_branch = Branch.objects.create(agency=foreign_agency, name="Foreign", code="FOREIGN")
    owner = User.objects.create_user(
        email="pricing-owner@test.local",
        password="safe-test-password",
        agency=agency,
        is_superuser=True,
    )
    foreign_owner = User.objects.create_user(
        email="foreign-pricing@test.local",
        password="safe-test-password",
        agency=foreign_agency,
        is_superuser=True,
    )
    customer = Customer.objects.create(
        agency=agency,
        branch=branch,
        kind=Customer.Kind.INDIVIDUAL,
        first_name="Test",
        last_name="Customer",
        created_by=owner,
    )
    trip = Trip.objects.create(
        agency=agency,
        branch=branch,
        code="pricing-trip",
        name="Pricing Trip",
        departure_date=date(2027, 3, 1),
        return_date=date(2027, 3, 10),
        created_by=owner,
    )
    stop = TripStop.objects.create(
        trip=trip,
        city=city,
        arrival_date=date(2027, 3, 1),
        departure_date=date(2027, 3, 5),
        order=1,
    )
    hotel = Hotel.objects.create(agency=agency, city=city, name="Snapshot Hotel")
    trip_hotel = TripHotel.objects.create(stop=stop, hotel=hotel, is_primary=True)
    room_type = RoomType.objects.create(agency=agency, code="double", name="Double")
    dzd = Currency.objects.get(code="DZD")
    eur = Currency.objects.get(code="EUR")
    AgencyCurrency.objects.create(agency=agency, currency=dzd, is_enabled=True, is_accounting=True)
    AgencyCurrency.objects.create(agency=agency, currency=eur, is_enabled=True)
    adult = PassengerCategory.objects.get(code="adt", is_system=True)
    hotel_price = TripHotelPrice.objects.create(
        agency=agency,
        trip_hotel=trip_hotel,
        room_type=room_type,
        passenger_category=adult,
        bed_basis=TripHotelPrice.BedBasis.STANDARD,
        amount=Decimal("100.0050"),
        currency=eur,
    )
    flight_price = SeasonalFlightPrice.objects.create(
        agency=agency,
        trip=trip,
        fare_name="Spring fare",
        sales_start_date=date(2026, 10, 1),
        sales_end_date=date(2027, 2, 15),
        passenger_category=adult,
        amount=Decimal("500.0000"),
        currency=eur,
    )
    quote = Quote.objects.create(
        agency=agency,
        branch=branch,
        code="Q-0001",
        customer=customer,
        trip=trip,
        currency=dzd,
        accounting_currency=dzd,
        accounting_exchange_rate=Decimal("1"),
        valid_until=date(2027, 2, 1),
        created_by=owner,
    )
    return locals()


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_money_uses_currency_precision_and_half_up(pricing_data):
    assert quantize_money(Decimal("12.345"), pricing_data["dzd"]) == Decimal("12.35")


def test_resolver_uses_selected_hotel_and_room_price(pricing_data):
    trip = pricing_data["trip"]
    trip.pricing_currency = pricing_data["eur"]
    trip.save(update_fields=["pricing_currency"])

    resolved = resolve_traveler_price(
        trip=trip,
        trip_hotel=pricing_data["trip_hotel"],
        room_type=pricing_data["room_type"],
        passenger_category=pricing_data["adult"],
        bed_requirement="REQUIRED",
        scope="HOTEL_STAY",
    )

    assert resolved.amount == Decimal("100.0050")
    assert resolved.currency_id == pricing_data["eur"].pk
    assert resolved.source_price_id == str(pricing_data["hotel_price"].pk)
    assert resolved.discount_amount == Decimal("0")


def test_resolver_uses_trip_level_child_and_infant_prices(pricing_data):
    child = PassengerCategory.objects.get(code="chd", is_system=True)
    infant = PassengerCategory.objects.get(code="inf", is_system=True)
    trip = pricing_data["trip"]
    trip.pricing_currency = pricing_data["eur"]
    trip.child_with_bed_discount = Decimal("18")
    trip.child_without_bed_price = Decimal("145")
    trip.infant_price = Decimal("85")
    trip.save(
        update_fields=[
            "pricing_currency",
            "child_with_bed_discount",
            "child_without_bed_price",
            "infant_price",
        ]
    )

    with_bed = resolve_traveler_price(
        trip=trip,
        trip_hotel=pricing_data["trip_hotel"],
        room_type=pricing_data["room_type"],
        passenger_category=child,
        bed_requirement="REQUIRED",
        scope="HOTEL_STAY",
    )
    without_bed = resolve_traveler_price(
        trip=trip,
        trip_hotel=pricing_data["trip_hotel"],
        room_type=pricing_data["room_type"],
        passenger_category=child,
        bed_requirement="NOT_REQUIRED",
    )
    infant_price = resolve_traveler_price(
        trip=trip,
        trip_hotel=pricing_data["trip_hotel"],
        room_type=pricing_data["room_type"],
        passenger_category=infant,
        bed_requirement="NOT_REQUIRED",
    )

    assert with_bed.amount == Decimal("82.0050")
    assert with_bed.discount_amount == Decimal("18")
    assert without_bed.amount == Decimal("145")
    assert without_bed.source_price_id is None
    assert infant_price.amount == Decimal("85")


def test_resolver_rejects_hotel_from_another_trip(pricing_data):
    other_trip = Trip.objects.create(
        agency=pricing_data["agency"],
        branch=pricing_data["branch"],
        code="other-resolver-trip",
        name="Other resolver trip",
        departure_date=date(2027, 4, 1),
        return_date=date(2027, 4, 5),
        created_by=pricing_data["owner"],
    )

    with pytest.raises(ValidationError, match="selected trip"):
        resolve_traveler_price(
            trip=other_trip,
            trip_hotel=pricing_data["trip_hotel"],
            room_type=pricing_data["room_type"],
            passenger_category=pricing_data["adult"],
            bed_requirement="REQUIRED",
        scope="HOTEL_STAY",
        )


def test_quote_line_freezes_source_values_when_added(pricing_data):
    line = add_price_to_quote(
        quote_id=pricing_data["quote"].pk,
        agency=pricing_data["agency"],
        price=pricing_data["hotel_price"],
        quantity=2,
        exchange_rate=Decimal("150.12345678"),
    )
    pricing_data["hotel_price"].amount = Decimal("999.0000")
    pricing_data["hotel_price"].save()
    line.refresh_from_db()

    assert line.source_unit_amount == Decimal("100.0050")
    assert line.source_snapshot["hotel"]["name"] == "Snapshot Hotel"
    assert line.total_amount == Decimal("30026.20")


def test_issue_creates_snapshot_that_survives_catalog_changes(pricing_data):
    line = add_price_to_quote(
        quote_id=pricing_data["quote"].pk,
        agency=pricing_data["agency"],
        price=pricing_data["flight_price"],
        quantity=2,
        exchange_rate=Decimal("150"),
    )
    quote = issue_quote(quote_id=pricing_data["quote"].pk, agency=pricing_data["agency"])
    original_payload = quote.snapshot.payload
    original_hash = quote.snapshot.sha256
    pricing_data["flight_price"].amount = Decimal("900.0000")
    pricing_data["flight_price"].save()
    quote.snapshot.refresh_from_db()

    assert quote.status == Quote.Status.ISSUED
    assert quote.snapshot.quote_total == Decimal("150000.0000")
    assert quote.snapshot.payload == original_payload
    assert quote.snapshot.sha256 == original_hash
    with pytest.raises(ValidationError):
        line.delete()
    with pytest.raises(ValidationError):
        quote.snapshot.delete()


def test_price_from_another_trip_cannot_be_quoted(pricing_data):
    other_trip = Trip.objects.create(
        agency=pricing_data["agency"],
        branch=pricing_data["branch"],
        code="other-trip",
        name="Other Trip",
        departure_date=date(2027, 4, 1),
        return_date=date(2027, 4, 5),
        created_by=pricing_data["owner"],
    )
    price = SeasonalFlightPrice.objects.create(
        agency=pricing_data["agency"],
        trip=other_trip,
        fare_name="Other",
        sales_start_date=date(2026, 10, 1),
        sales_end_date=date(2027, 3, 1),
        passenger_category=pricing_data["adult"],
        amount=Decimal("100"),
        currency=pricing_data["eur"],
    )

    with pytest.raises(ValidationError):
        add_price_to_quote(
            quote_id=pricing_data["quote"].pk,
            agency=pricing_data["agency"],
            price=price,
            quantity=1,
            exchange_rate=Decimal("150"),
        )


def test_quote_api_issues_and_transitions_to_accepted(pricing_data):
    client = client_for(pricing_data["owner"])
    add_response = client.post(
        reverse("quote-add-flight-price", args=[pricing_data["quote"].pk]),
        {"price_id": pricing_data["flight_price"].pk, "quantity": 1, "exchange_rate": "150"},
        format="json",
    )
    issue_response = client.post(
        reverse("quote-issue", args=[pricing_data["quote"].pk]), {}, format="json"
    )
    accept_response = client.post(
        reverse("quote-transition", args=[pricing_data["quote"].pk]),
        {"status": Quote.Status.ACCEPTED},
        format="json",
    )

    assert add_response.status_code == 201
    assert issue_response.status_code == 200
    assert len(issue_response.data["snapshot"]["sha256"]) == 64
    assert accept_response.status_code == 200
    assert accept_response.data["status"] == Quote.Status.ACCEPTED


def test_pricing_api_never_exposes_another_agency(pricing_data):
    foreign_trip = Trip.objects.create(
        agency=pricing_data["foreign_agency"],
        branch=pricing_data["foreign_branch"],
        code="foreign-price-trip",
        name="Foreign Price Trip",
        departure_date=date(2027, 5, 1),
        return_date=date(2027, 5, 5),
        created_by=pricing_data["foreign_owner"],
    )
    foreign_price = SeasonalFlightPrice.objects.create(
        agency=pricing_data["foreign_agency"],
        trip=foreign_trip,
        fare_name="Foreign fare",
        sales_start_date=date(2026, 10, 1),
        sales_end_date=date(2027, 4, 1),
        passenger_category=pricing_data["adult"],
        amount=Decimal("100"),
        currency=pricing_data["eur"],
    )

    response = client_for(pricing_data["owner"]).get(reverse("flight-price-list"))

    returned_ids = {str(item["id"]) for item in response.data["results"]}
    assert str(pricing_data["flight_price"].pk) in returned_ids
    assert str(foreign_price.pk) not in returned_ids


def test_issued_quote_line_cannot_be_changed(pricing_data):
    line = add_price_to_quote(
        quote_id=pricing_data["quote"].pk,
        agency=pricing_data["agency"],
        price=pricing_data["flight_price"],
        quantity=1,
        exchange_rate=Decimal("150"),
    )
    issue_quote(quote_id=pricing_data["quote"].pk, agency=pricing_data["agency"])
    line.description = "Changed"

    with pytest.raises(ValidationError):
        line.save()

    assert QuoteLine.objects.get(pk=line.pk).description != "Changed"


def test_issued_quote_terms_cannot_be_changed(pricing_data):
    add_price_to_quote(
        quote_id=pricing_data["quote"].pk,
        agency=pricing_data["agency"],
        price=pricing_data["flight_price"],
        quantity=1,
        exchange_rate=Decimal("150"),
    )
    quote = issue_quote(quote_id=pricing_data["quote"].pk, agency=pricing_data["agency"])
    quote.valid_until = date(2027, 2, 2)

    with pytest.raises(ValidationError):
        quote.save()
