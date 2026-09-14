from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from bookings.models import (
    Booking,
    BookingAccommodation,
    BookingTraveler,
    BookingTravelerCharge,
)
from bookings.services import (
    add_booking_traveler,
    add_charge_discount,
    add_inline_booking_traveler,
    add_room_group,
    add_traveler_charge,
    assign_room_traveler,
    confirm_booking_draft,
    create_booking_draft,
    create_booking_from_quote,
    create_direct_booking,
    transition_booking,
)
from bookings.api.serializers import BookingSerializer
from catalog.models import Airline, Hotel, RoomType, Supplier
from customers.models import Customer
from finance.models import AgencyCashEntry, ExchangeRate, FinancialTransaction, PaymentAllocation, TripExpense
from finance.services import (
    booking_financial_summary,
    cash_flow_summary,
    post_cash_entry,
    post_expense_payment,
    post_transaction,
    reverse_expense_payment,
    reverse_transaction,
)
from organizations.models import Agency, Branch
from partners.models import Partner, PartnerAllocation, PartnerCommission
from partners.services import (
    assign_allocation,
    post_commission_payment,
    reverse_commission_payment,
    transition_commission,
)
from pricing.models import Quote, TripHotelPrice
from pricing.services import add_price_to_quote, issue_quote, transition_quote
from reference.models import (
    AgencyCurrency,
    City,
    Country,
    Currency,
    PassengerCategory,
    PaymentMethod,
)
from travelers.models import Passport, Traveler
from travelers.services import save_passport
from trips.models import (
    Trip,
    TripAllocationRoom,
    TripFlight,
    TripHotel,
    TripRoomAssignment,
    TripStop,
)


@pytest.fixture
def booking_data(db):
    country = Country.objects.create(name="Booking Country", code="BC")
    origin = City.objects.create(country=country, name="Booking Origin")
    destination = City.objects.create(country=country, name="Booking Destination")
    agency = Agency.objects.create(name="Booking Travel", slug="booking-travel")
    foreign_agency = Agency.objects.create(name="Other Booking", slug="other-booking")
    branch = Branch.objects.create(agency=agency, name="Main", code="MAIN")
    foreign_branch = Branch.objects.create(agency=foreign_agency, name="Other", code="OTHER")
    owner = User.objects.create_user(
        email="booking-owner@test.local",
        password="safe-test-password",
        agency=agency,
        is_superuser=True,
    )
    foreign_owner = User.objects.create_user(
        email="other-booking@test.local",
        password="safe-test-password",
        agency=foreign_agency,
        is_superuser=True,
    )
    customer = Customer.objects.create(
        agency=agency,
        branch=branch,
        kind=Customer.Kind.INDIVIDUAL,
        first_name="Booking",
        last_name="Customer",
        phone="0550000001",
        created_by=owner,
    )
    trip = Trip.objects.create(
        agency=agency,
        branch=branch,
        code="booking-trip",
        name="Booking Trip",
        departure_date=date(2027, 6, 1),
        return_date=date(2027, 6, 10),
        created_by=owner,
    )
    stop = TripStop.objects.create(
        trip=trip,
        city=destination,
        arrival_date=date(2027, 6, 1),
        departure_date=date(2027, 6, 10),
        order=1,
    )
    hotel = Hotel.objects.create(agency=agency, city=destination, name="Booking Hotel")
    trip_hotel = TripHotel.objects.create(stop=stop, hotel=hotel, is_primary=True)
    room_type = RoomType.objects.create(agency=agency, code="triple", name="Triple")
    airline = Airline.objects.get(iata_code="AH")
    trip_flight = TripFlight.objects.create(
        trip=trip,
        airline=airline,
        direction=TripFlight.Direction.OUTBOUND,
        flight_number="AH200",
        origin_city=origin,
        destination_city=destination,
        origin_airport_code="ORG",
        destination_airport_code="DST",
        departure_at=datetime(2027, 6, 1, 8, tzinfo=UTC),
        arrival_at=datetime(2027, 6, 1, 10, tzinfo=UTC),
        order=1,
    )
    dzd = Currency.objects.get(code="DZD")
    AgencyCurrency.objects.create(agency=agency, currency=dzd, is_enabled=True, is_accounting=True)
    adult = PassengerCategory.objects.get(code="adt", is_system=True)
    hotel_price = TripHotelPrice.objects.create(
        agency=agency,
        trip_hotel=trip_hotel,
        room_type=room_type,
        passenger_category=adult,
        bed_basis=TripHotelPrice.BedBasis.STANDARD,
        amount=Decimal("120000"),
        currency=dzd,
    )
    quote = Quote.objects.create(
        agency=agency,
        branch=branch,
        code="Q-BOOK-1",
        customer=customer,
        trip=trip,
        currency=dzd,
        accounting_currency=dzd,
        accounting_exchange_rate=Decimal("1"),
        valid_until=date(2027, 5, 1),
        created_by=owner,
    )
    add_price_to_quote(
        quote_id=quote.pk,
        agency=agency,
        price=hotel_price,
        quantity=2,
        exchange_rate=Decimal("1"),
    )
    issue_quote(quote_id=quote.pk, agency=agency)
    transition_quote(quote_id=quote.pk, agency=agency, target_status=Quote.Status.ACCEPTED)
    traveler = Traveler.objects.create(
        agency=agency, branch=branch, created_by=owner, phone="0550000000"
    )
    return locals()


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_booking(data, code="B-0001"):
    return create_booking_from_quote(
        quote_id=data["quote"].pk,
        agency=data["agency"],
        actor=data["owner"],
        code=code,
    )


def test_accepted_quote_converts_to_frozen_booking(booking_data):
    booking = create_booking(booking_data)
    accommodation = booking.accommodations.get()

    assert booking.status == Booking.Status.CONFIRMED
    assert booking.total_amount == Decimal("240000.0000")
    assert accommodation.trip_hotel == booking_data["trip_hotel"]
    assert accommodation.quantity == 2
    assert booking.flights.get().trip_flight == booking_data["trip_flight"]
    assert booking.snapshot.payload["source_quote"]["snapshot_sha256"] == (
        booking_data["quote"].snapshot.sha256
    )


def test_cash_flow_report_captures_agency_and_trip_entries(booking_data):
    payment_method = PaymentMethod.objects.get(code="cash", is_system=True)
    post_cash_entry(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        branch=booking_data["branch"],
        trip=booking_data["trip"],
        direction=AgencyCashEntry.Direction.IN,
        category=AgencyCashEntry.Category.OWNER_FUNDS,
        description="Trip deposit",
        amount=Decimal("10000"),
        currency=booking_data["dzd"],
        payment_method=payment_method,
        entry_date=date(2027, 5, 1),
    )
    post_cash_entry(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        branch=booking_data["branch"],
        direction=AgencyCashEntry.Direction.OUT,
        category=AgencyCashEntry.Category.OPERATING_COST,
        description="Office rent",
        amount=Decimal("2500"),
        currency=booking_data["dzd"],
        payment_method=payment_method,
        entry_date=date(2027, 5, 2),
    )

    agency_report = cash_flow_summary(agency=booking_data["agency"])
    trip_report = cash_flow_summary(agency=booking_data["agency"], trip_id=booking_data["trip"].pk)

    assert agency_report["totals_by_currency"]["DZD"] == {
        "inflow": Decimal("10000"),
        "outflow": Decimal("2500"),
        "net": Decimal("7500"),
    }
    assert trip_report["totals_by_currency"]["DZD"]["net"] == Decimal("10000")
    assert len(trip_report["entries"]) == 1


def test_cash_entry_is_immutable(booking_data):
    payment_method = PaymentMethod.objects.get(code="cash", is_system=True)
    entry = post_cash_entry(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        branch=booking_data["branch"],
        direction=AgencyCashEntry.Direction.OUT,
        category=AgencyCashEntry.Category.TAX,
        description="Tax payment",
        amount=Decimal("1000"),
        currency=booking_data["dzd"],
        payment_method=payment_method,
        entry_date=date(2027, 5, 3),
    )
    entry.description = "Changed"
    with pytest.raises(ValidationError, match="immutable"):
        entry.save()


def test_direct_booking_freezes_selected_prices_without_quote(booking_data):
    booking = create_direct_booking(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        branch=booking_data["branch"],
        customer=booking_data["customer"],
        trip=booking_data["trip"],
        code="B-DIRECT-1",
        currency=booking_data["dzd"],
        accounting_currency=booking_data["dzd"],
        accounting_exchange_rate=Decimal("1"),
        price_lines=[
            {
                "price_id": booking_data["hotel_price"].pk,
                "quantity": 2,
                "exchange_rate": Decimal("1"),
            }
        ],
    )
    assert booking.source_quote is None
    assert booking.total_amount == Decimal("240000")
    assert booking.accommodations.get().source_quote_line is None
    assert booking.snapshot.payload["source"] == "DIRECT"
    assert booking.snapshot.payload["source_quote"] is None


def test_direct_booking_payment_does_not_lock_nullable_source_quote(booking_data):
    booking = create_direct_booking(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        branch=booking_data["branch"],
        customer=booking_data["customer"],
        trip=booking_data["trip"],
        code="B-DIRECT-PAYMENT",
        currency=booking_data["dzd"],
        accounting_currency=booking_data["dzd"],
        accounting_exchange_rate=Decimal("1"),
        price_lines=[
            {
                "price_id": booking_data["hotel_price"].pk,
                "quantity": 2,
                "exchange_rate": Decimal("1"),
            }
        ],
    )
    eur = Currency.objects.get(code="EUR")
    AgencyCurrency.objects.get_or_create(agency=booking_data["agency"], currency=eur, is_enabled=True)
    method = PaymentMethod.objects.filter(is_system=True).first()

    prepare_payment_passports(booking_data, booking)
    payment = post_transaction(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        booking_id=booking.pk,
        kind=FinancialTransaction.Kind.PAYMENT,
        amount=Decimal("100"),
        currency=eur,
        booking_exchange_rate=Decimal("150"),
        payment_method=method,
        transaction_date=date(2027, 1, 1),
    )

    assert payment.booking_id == booking.pk
    assert booking.source_quote is None


def test_direct_booking_api(booking_data):
    response = client_for(booking_data["owner"]).post(
        reverse("booking-direct"),
        {
            "code": "B-DIRECT-API",
            "branch": booking_data["branch"].pk,
            "customer": booking_data["customer"].pk,
            "trip": booking_data["trip"].pk,
            "currency": "DZD",
            "accounting_currency": "DZD",
            "accounting_exchange_rate": "1",
            "price_lines": [
                {"price_id": booking_data["hotel_price"].pk, "quantity": 1, "exchange_rate": "1"}
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["source_quote"] is None


def test_direct_booking_creates_inline_customer_atomically(booking_data):
    response = client_for(booking_data["owner"]).post(
        reverse("booking-direct"),
        {
            "code": "B-NEW-CUSTOMER",
            "branch": booking_data["branch"].pk,
            "new_customer": {
                "kind": "INDIVIDUAL",
                "first_name": "New",
                "last_name": "Pilgrim",
                "phone": "0550111222",
            },
            "trip": booking_data["trip"].pk,
            "currency": "DZD",
            "accounting_currency": "DZD",
            "accounting_exchange_rate": "1",
            "price_lines": [
                {
                    "price_id": booking_data["hotel_price"].pk,
                    "quantity": 1,
                    "exchange_rate": "1",
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["customer_name"] == "New Pilgrim"
    assert Customer.objects.filter(agency=booking_data["agency"], first_name="New").exists()


def test_booking_reference_is_generated_when_omitted(booking_data):
    response = client_for(booking_data["owner"]).post(
        reverse("booking-direct"),
        {
            "branch": booking_data["branch"].pk,
            "customer": booking_data["customer"].pk,
            "trip": booking_data["trip"].pk,
            "currency": "DZD",
            "accounting_currency": "DZD",
            "accounting_exchange_rate": "1",
            "price_lines": [
                {
                    "price_id": booking_data["hotel_price"].pk,
                    "quantity": 1,
                    "exchange_rate": "1",
                }
            ],
        },
        format="json",
    )
    assert response.status_code == 201, response.data
    assert response.data["code"].startswith("B-")


def test_guided_booking_draft_freezes_travelers_rooms_prices_and_discounts(booking_data):
    data = booking_data
    booking = create_booking_draft(
        agency=data["agency"],
        actor=data["owner"],
        branch=data["branch"],
        customer=data["customer"],
        trip=data["trip"],
        currency=data["dzd"],
        accounting_currency=data["dzd"],
        accounting_exchange_rate=Decimal("1"),
    )
    traveler = add_inline_booking_traveler(
        booking_id=booking.pk,
        agency=data["agency"],
        actor=data["owner"],
        first_name="Ahmed",
        last_name="Pilgrim",
        passenger_category=data["adult"],
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    save_passport(
        traveler=traveler.traveler,
        actor=data["owner"],
        status=Passport.Status.CURRENT,
        passport_number="GUIDED100",
        first_name="Ahmed",
        middle_name="",
        last_name="Pilgrim",
        birth_date=date(1990, 1, 1),
        birth_place="",
        birth_country=data["country"],
        nationality=data["country"],
        gender=Passport.Gender.MALE,
        issue_date=date(2025, 1, 1),
        expiry_date=date(2028, 1, 1),
        issuing_country=data["country"],
        issue_place="",
    )
    room = add_room_group(
        booking_id=booking.pk,
        agency=data["agency"],
        trip_hotel=data["trip_hotel"],
        room_type=data["room_type"],
        label="Room 1",
        capacity=2,
    )
    charge = add_traveler_charge(
        booking_id=booking.pk,
        booking_traveler_id=traveler.pk,
        agency=data["agency"],
        kind=BookingTravelerCharge.Kind.ACCOMMODATION,
        description="Booking Hotel · Triple",
        source_price=data["hotel_price"],
        base_amount=Decimal("120000"),
        currency=data["dzd"],
    )
    assign_room_traveler(
        booking_id=booking.pk,
        room_id=room.pk,
        booking_traveler_id=traveler.pk,
        agency=data["agency"],
    )
    add_charge_discount(
        booking_id=booking.pk,
        charge_id=charge.pk,
        agency=data["agency"],
        actor=data["owner"],
        kind="AMOUNT",
        value=Decimal("5000"),
        reason="Family discount",
    )

    booking.refresh_from_db()
    assert booking.total_amount == Decimal("115000.0000")
    assert booking.accounting_total_amount == Decimal("115000.0000")

    confirmed = confirm_booking_draft(booking_id=booking.pk, agency=data["agency"])

    assert confirmed.status == Booking.Status.CONFIRMED
    assert confirmed.total_amount == Decimal("115000.0000")
    assert confirmed.snapshot.payload["travelers"][0]["name"] == "Ahmed Pilgrim"
    assert confirmed.snapshot.payload["charges"][0]["discount_amount"] == "5000.0000"
    assert confirmed.accommodations.get().total_amount == Decimal("115000.0000")


def test_commercial_confirmation_allows_passport_and_allocation_follow_up(booking_data):
    data = booking_data
    booking = create_booking_draft(
        agency=data["agency"],
        actor=data["owner"],
        branch=data["branch"],
        customer=data["customer"],
        trip=data["trip"],
        currency=data["dzd"],
        accounting_currency=data["dzd"],
        accounting_exchange_rate=Decimal("1"),
    )
    traveler = add_inline_booking_traveler(
        booking_id=booking.pk,
        agency=data["agency"],
        actor=data["owner"],
        first_name="Follow",
        last_name="Up",
        birth_date=date(1990, 1, 1),
        gender=Passport.Gender.FEMALE,
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    add_traveler_charge(
        booking_id=booking.pk,
        booking_traveler_id=traveler.pk,
        agency=data["agency"],
        kind=BookingTravelerCharge.Kind.ACCOMMODATION,
        description="Commercial package",
        source_price=data["hotel_price"],
        base_amount=data["hotel_price"].amount,
        currency=data["dzd"],
    )

    response = client_for(data["owner"]).get(
        reverse("booking-detail", args=[booking.pk])
    )
    assert response.status_code == 200
    assert response.data["readiness"]["commercial_ready"] is True
    assert response.data["readiness"]["operational_ready"] is False
    assert response.data["readiness"]["missing_passports"] == 1
    assert response.data["readiness"]["allocation_status"] == "NOT_STARTED"

    confirmed = confirm_booking_draft(booking_id=booking.pk, agency=data["agency"])

    assert confirmed.status == Booking.Status.CONFIRMED
    assert confirmed.snapshot.payload["travelers"][0]["passport"] is None
    assert confirmed.snapshot.payload["rooms"] == []


def test_guided_booking_draft_api_creates_customer_and_empty_draft(booking_data):
    data = booking_data
    response = client_for(data["owner"]).post(
        reverse("booking-draft"),
        {
            "branch": data["branch"].pk,
            "new_customer": {
                "kind": "INDIVIDUAL",
                "first_name": "Group",
                "last_name": "Leader",
                "phone": "0550123456",
            },
            "trip": data["trip"].pk,
            "currency": "DZD",
            "accounting_currency": "DZD",
            "accounting_exchange_rate": "1",
        },
        format="json",
    )

    assert response.status_code == 201, response.data
    assert response.data["status"] == Booking.Status.DRAFT
    assert response.data["customer_name"] == "Group Leader"
    assert response.data["travelers"] == []
    assert response.data["room_groups"] == []


def test_guided_booking_cannot_confirm_without_individual_prices(booking_data):
    data = booking_data
    booking = create_booking_draft(
        agency=data["agency"],
        actor=data["owner"],
        branch=data["branch"],
        customer=data["customer"],
        trip=data["trip"],
        currency=data["dzd"],
        accounting_currency=data["dzd"],
        accounting_exchange_rate=Decimal("1"),
    )
    traveler = add_inline_booking_traveler(
        booking_id=booking.pk,
        agency=data["agency"],
        actor=data["owner"],
        first_name="No",
        last_name="Price",
        passenger_category=data["adult"],
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    save_passport(
        traveler=traveler.traveler,
        actor=data["owner"],
        status=Passport.Status.CURRENT,
        passport_number="NOPRICE100",
        first_name="No",
        middle_name="",
        last_name="Price",
        birth_date=date(1990, 1, 1),
        birth_place="",
        birth_country=data["country"],
        nationality=data["country"],
        gender=Passport.Gender.MALE,
        issue_date=date(2025, 1, 1),
        expiry_date=date(2028, 1, 1),
        issuing_country=data["country"],
        issue_place="",
    )

    with pytest.raises(ValidationError, match="Every traveler requires"):
        confirm_booking_draft(booking_id=booking.pk, agency=data["agency"])


def test_confirmation_explains_the_exact_hotel_price_category_mismatch(booking_data):
    data = booking_data
    child = PassengerCategory.objects.get(code="chd", is_system=True)
    booking = create_booking_draft(
        agency=data["agency"],
        actor=data["owner"],
        branch=data["branch"],
        customer=data["customer"],
        trip=data["trip"],
        currency=data["dzd"],
        accounting_currency=data["dzd"],
        accounting_exchange_rate=Decimal("1"),
    )
    traveler = add_inline_booking_traveler(
        booking_id=booking.pk,
        agency=data["agency"],
        actor=data["owner"],
        first_name="Child",
        last_name="Traveler",
        passenger_category=child,
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    save_passport(
        traveler=traveler.traveler,
        actor=data["owner"],
        status=Passport.Status.CURRENT,
        passport_number="CHILD100",
        first_name="Child",
        middle_name="",
        last_name="Traveler",
        birth_date=date(2017, 1, 1),
        birth_place="",
        birth_country=data["country"],
        nationality=data["country"],
        gender=Passport.Gender.FEMALE,
        issue_date=date(2025, 1, 1),
        expiry_date=date(2028, 1, 1),
        issuing_country=data["country"],
        issue_place="",
    )
    add_traveler_charge(
        booking_id=booking.pk,
        booking_traveler_id=traveler.pk,
        agency=data["agency"],
        kind=BookingTravelerCharge.Kind.ACCOMMODATION,
        description="Adult hotel price selected for a child",
        source_price=data["hotel_price"],
        base_amount=data["hotel_price"].amount,
        currency=data["dzd"],
    )

    with pytest.raises(ValidationError) as error:
        confirm_booking_draft(booking_id=booking.pk, agency=data["agency"])

    message = str(error.value)
    assert "Child Traveler" in message
    assert "traveler category is CHD" in message
    assert "selected price is ADT" in message
    assert "Booking Hotel" in message
    assert "room type Triple" in message
    assert "120000.0000 DZD" in message
    assert "No matching CHD price is configured" in message


def test_payment_can_be_allocated_to_individual_travelers(booking_data):
    data = booking_data
    booking = create_booking(data, "B-ALLOCATED")
    traveler = add_booking_traveler(
        booking_id=booking.pk,
        agency=data["agency"],
        traveler=data["traveler"],
        passenger_category=data["adult"],
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    method = PaymentMethod.objects.filter(is_system=True).first()
    prepare_payment_passports(booking_data, booking)
    entry = post_transaction(
        agency=data["agency"],
        actor=data["owner"],
        booking_id=booking.pk,
        kind=FinancialTransaction.Kind.PAYMENT,
        amount=Decimal("50000"),
        currency=data["dzd"],
        booking_exchange_rate=Decimal("1"),
        payment_method=method,
        transaction_date=date(2027, 1, 1),
        allocations=[{"booking_traveler": traveler.pk, "amount": Decimal("50000")}],
    )

    assert PaymentAllocation.objects.get(transaction=entry).booking_traveler == traveler
    balance = booking_financial_summary(booking)["traveler_balances"][0]
    assert balance["paid_amount"] == Decimal("50000")


def test_quote_can_only_convert_once(booking_data):
    create_booking(booking_data)

    with pytest.raises(ValidationError):
        create_booking(booking_data, code="B-0002")


def test_non_accepted_quote_cannot_convert(booking_data):
    booking_data["quote"].status = Quote.Status.ISSUED
    Quote.objects.filter(pk=booking_data["quote"].pk).update(status=Quote.Status.ISSUED)

    with pytest.raises(ValidationError):
        create_booking(booking_data)


def test_customer_and_booking_traveler_are_independent(booking_data):
    booking = create_booking(booking_data)
    link = add_booking_traveler(
        booking_id=booking.pk,
        agency=booking_data["agency"],
        traveler=booking_data["traveler"],
        passenger_category=booking_data["adult"],
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )

    assert link.traveler == booking_data["traveler"]
    assert booking.customer == booking_data["customer"]
    assert not hasattr(booking.customer, "traveler_id")


def test_completion_requires_a_traveler(booking_data):
    booking = create_booking(booking_data)

    with pytest.raises(ValidationError):
        transition_booking(
            booking_id=booking.pk,
            agency=booking_data["agency"],
            target_status=Booking.Status.COMPLETED,
        )


def test_cancellation_requires_reason_and_is_terminal(booking_data):
    booking = create_booking(booking_data)
    with pytest.raises(ValidationError):
        transition_booking(
            booking_id=booking.pk,
            agency=booking_data["agency"],
            target_status=Booking.Status.CANCELLED,
        )
    cancelled = transition_booking(
        booking_id=booking.pk,
        agency=booking_data["agency"],
        target_status=Booking.Status.CANCELLED,
        cancellation_reason="Customer request",
    )

    assert cancelled.cancellation_reason == "Customer request"
    with pytest.raises(ValidationError):
        transition_booking(
            booking_id=booking.pk,
            agency=booking_data["agency"],
            target_status=Booking.Status.COMPLETED,
        )


def test_booking_transition_api_maps_status_to_service_target(booking_data):
    booking = create_booking(booking_data, "B-API-CANCEL")
    client = client_for(booking_data["owner"])

    response = client.post(
        reverse("booking-transition", kwargs={"pk": booking.pk}),
        {"status": Booking.Status.CANCELLED, "cancellation_reason": "معلومات غير صحيحة"},
        format="json",
    )

    assert response.status_code == 200
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CANCELLED
    assert booking.cancellation_reason == "معلومات غير صحيحة"


def test_booking_readiness_names_missing_room_stops(booking_data):
    booking = create_booking(booking_data, "B-READINESS-ROOMS")
    traveler = add_booking_traveler(
        booking_id=booking.pk,
        agency=booking_data["agency"],
        traveler=booking_data["traveler"],
        passenger_category=booking_data["adult"],
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    serializer = BookingSerializer(booking)
    issues = serializer.data["readiness"]["completion"]

    assert issues[0]["id"] == str(traveler.pk)
    assert "Room allocation is incomplete for Booking Destination" in issues[0]["issues"]


def test_cancellation_releases_trip_room_allocations(booking_data):
    data = booking_data
    booking = create_booking(data, "B-CANCEL-ALLOCATED")
    traveler = add_booking_traveler(
        booking_id=booking.pk,
        agency=data["agency"],
        traveler=data["traveler"],
        passenger_category=data["adult"],
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    room = TripAllocationRoom.objects.create(
        trip_hotel=data["trip_hotel"],
        room_type=data["room_type"],
        label="Operational room",
        standard_beds=3,
        created_by=data["owner"],
    )
    assignment = TripRoomAssignment.objects.create(
        stop=data["stop"],
        room=room,
        booking_traveler=traveler,
        bed_number=1,
        assigned_by=data["owner"],
    )

    transition_booking(
        booking_id=booking.pk,
        agency=data["agency"],
        target_status=Booking.Status.CANCELLED,
        cancellation_reason="Customer request",
    )

    assert not TripRoomAssignment.objects.filter(pk=assignment.pk).exists()


def test_booking_commercial_values_and_accommodation_are_immutable(booking_data):
    booking = create_booking(booking_data)
    booking.total_amount = Decimal("1")
    accommodation = booking.accommodations.get()

    with pytest.raises(ValidationError):
        booking.save()
    with pytest.raises(ValidationError):
        accommodation.delete()


def test_booking_api_conversion_and_traveler_assignment(booking_data):
    client = client_for(booking_data["owner"])
    response = client.post(
        reverse("booking-from-quote"),
        {"quote_id": booking_data["quote"].pk, "code": "B-API-1"},
        format="json",
    )
    traveler_response = client.post(
        reverse("booking-add-traveler", args=[response.data["id"]]),
        {
            "traveler": booking_data["traveler"].pk,
            "passenger_category": booking_data["adult"].pk,
            "bed_requirement": BookingTraveler.BedRequirement.REQUIRED,
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["accommodations"][0]["hotel_name"] == "Booking Hotel"
    assert traveler_response.status_code == 201
    assert traveler_response.data["traveler_count"] == 1


def test_booking_list_is_tenant_scoped(booking_data):
    booking = create_booking(booking_data)
    response = client_for(booking_data["foreign_owner"]).get(reverse("booking-list"))

    assert response.status_code == 200
    assert str(booking.pk) not in {str(item["id"]) for item in response.data["results"]}


def test_booking_list_reports_paid_and_remaining_balance(booking_data):
    booking = create_booking(booking_data)
    post_payment(booking_data, booking)

    response = client_for(booking_data["owner"]).get(reverse("booking-list"))
    item = next(item for item in response.data["results"] if str(item["id"]) == str(booking.pk))

    assert response.status_code == 200
    assert item["paid_amount"] == Decimal("15000.0000")
    assert item["remaining_amount"] == Decimal("225000.0000")


def test_accommodation_is_not_a_physical_room(booking_data):
    create_booking(booking_data)

    assert "room" not in {field.name for field in BookingAccommodation._meta.fields}


def post_payment(data, booking, amount="100", rate="150"):
    prepare_payment_passports(data, booking)
    eur = Currency.objects.get(code="EUR")
    AgencyCurrency.objects.get_or_create(agency=data["agency"], currency=eur, is_enabled=True)
    return post_transaction(
        agency=data["agency"],
        actor=data["owner"],
        booking_id=booking.pk,
        kind=FinancialTransaction.Kind.PAYMENT,
        amount=Decimal(amount),
        currency=eur,
        booking_exchange_rate=Decimal(rate),
        payment_method=PaymentMethod.objects.filter(is_system=True).first(),
        transaction_date=date(2027, 1, 1),
        reference="BANK-001",
    )


def test_multi_currency_payment_preserves_original_and_converted_values(booking_data):
    booking = create_booking(booking_data)
    add_booking_traveler(
        booking_id=booking.pk,
        agency=booking_data["agency"],
        traveler=booking_data["traveler"],
        passenger_category=booking_data["adult"],
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    payment = post_payment(booking_data, booking)
    summary = booking_financial_summary(booking)

    assert payment.amount == Decimal("100")
    assert payment.currency_id == "EUR"
    assert payment.booking_exchange_rate == Decimal("150")
    assert payment.booking_amount == Decimal("15000.0000")
    assert summary["paid_amount"] == Decimal("15000.0000")
    assert summary["remaining_amount"] == Decimal("225000.0000")


def test_refund_and_reversal_are_signed_immutable_ledger_entries(booking_data):
    booking = create_booking(booking_data)
    payment = post_payment(booking_data, booking)
    refund = post_transaction(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        booking_id=booking.pk,
        kind=FinancialTransaction.Kind.REFUND,
        amount=Decimal("20"),
        currency=Currency.objects.get(code="EUR"),
        booking_exchange_rate=Decimal("150"),
        payment_method=PaymentMethod.objects.filter(is_system=True).first(),
        transaction_date=date(2027, 1, 2),
    )
    reversal = reverse_transaction(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        transaction_id=refund.pk,
        transaction_date=date(2027, 1, 3),
        reason="Refund entered by mistake",
    )

    assert booking_financial_summary(booking)["paid_amount"] == Decimal("15000.0000")
    assert reversal.reverses == refund
    with pytest.raises(ValidationError):
        payment.delete()


def test_payment_cannot_exceed_remaining_balance(booking_data):
    booking = create_booking(booking_data)

    with pytest.raises(ValidationError):
        post_payment(booking_data, booking, amount="2000", rate="150")


def test_finance_api_posts_payment_and_returns_receipt(booking_data):
    booking = create_booking(booking_data)
    prepare_payment_passports(booking_data, booking)
    eur = Currency.objects.get(code="EUR")
    AgencyCurrency.objects.create(agency=booking_data["agency"], currency=eur, is_enabled=True)
    method = PaymentMethod.objects.filter(is_system=True).first()
    client = client_for(booking_data["owner"])
    response = client.post(
        reverse("financial-transaction-payments"),
        {
            "booking": booking.pk,
            "amount": "100.00",
            "currency": "EUR",
            "booking_exchange_rate": "150",
            "payment_method": method.pk,
            "transaction_date": "2027-01-01",
        },
        format="json",
    )
    receipt = client.get(reverse("financial-transaction-receipt", args=[response.data["id"]]))

    assert response.status_code == 201
    assert receipt.status_code == 200
    assert receipt.data["booking_code"] == booking.code
    assert receipt.data["financial_summary"]["paid_amount"] == "15000.0000"
    assert receipt.data["financial_summary"]["remaining_amount"] == "225000.0000"


def test_finance_receipt_falls_back_to_accommodations_when_room_groups_are_missing(booking_data):
    booking = create_direct_booking(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        branch=booking_data["branch"],
        customer=booking_data["customer"],
        trip=booking_data["trip"],
        code="B-RECEIPT-FALLBACK",
        currency=booking_data["dzd"],
        accounting_currency=booking_data["dzd"],
        accounting_exchange_rate=Decimal("1"),
        price_lines=[
            {
                "price_id": booking_data["hotel_price"].pk,
                "quantity": 1,
                "exchange_rate": Decimal("1"),
            }
        ],
    )
    method = PaymentMethod.objects.filter(is_system=True).first()
    prepare_payment_passports(booking_data, booking)
    payment = post_transaction(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        booking_id=booking.pk,
        kind=FinancialTransaction.Kind.PAYMENT,
        amount=Decimal("100"),
        currency=booking_data["dzd"],
        booking_exchange_rate=Decimal("1"),
        payment_method=method,
        transaction_date=date(2027, 1, 1),
    )

    client = client_for(booking_data["owner"])
    response = client.get(reverse("financial-transaction-receipt", args=[payment.pk]))

    assert response.status_code == 200
    assert response.data["hotels"] == ["Booking Destination: Booking Hotel"]
    assert response.data["room_types"] == ["Triple"]


def test_finance_list_is_tenant_scoped(booking_data):
    booking = create_booking(booking_data)
    payment = post_payment(booking_data, booking)
    response = client_for(booking_data["foreign_owner"]).get(reverse("financial-transaction-list"))

    assert str(payment.pk) not in {str(item["id"]) for item in response.data["results"]}


def test_historical_exchange_rate_is_immutable(booking_data):
    eur = Currency.objects.get(code="EUR")
    rate = ExchangeRate.objects.create(
        agency=booking_data["agency"],
        source_currency=eur,
        target_currency=booking_data["dzd"],
        rate=Decimal("150"),
        effective_date=date(2027, 1, 1),
        created_by=booking_data["owner"],
    )
    rate.rate = Decimal("160")

    with pytest.raises(ValidationError):
        rate.save()


def test_partner_allocation_usage_and_remaining_are_calculated(booking_data):
    booking = create_booking(booking_data)
    partner = Partner.objects.create(
        agency=booking_data["agency"],
        branch=booking_data["branch"],
        name="Partner One",
        created_by=booking_data["owner"],
    )
    allocation = PartnerAllocation.objects.create(
        agency=booking_data["agency"],
        partner=partner,
        trip=booking_data["trip"],
        kind=PartnerAllocation.Kind.PACKAGE,
        quantity=3,
        created_by=booking_data["owner"],
    )
    assign_allocation(
        allocation_id=allocation.pk,
        booking=booking,
        quantity=2,
        agency=booking_data["agency"],
        actor=booking_data["owner"],
    )
    assert allocation.used_quantity == 2
    assert allocation.remaining_quantity == 1
    with pytest.raises(ValidationError):
        assign_allocation(
            allocation_id=allocation.pk,
            booking=booking,
            quantity=2,
            agency=booking_data["agency"],
            actor=booking_data["owner"],
        )


def test_commission_payment_balance_and_reversal(booking_data):
    booking = create_booking(booking_data)
    partner = Partner.objects.create(
        agency=booking_data["agency"],
        branch=booking_data["branch"],
        name="Commission Partner",
        created_by=booking_data["owner"],
    )
    commission = PartnerCommission.objects.create(
        agency=booking_data["agency"],
        partner=partner,
        booking=booking,
        amount=Decimal("10000"),
        currency=booking_data["dzd"],
        created_by=booking_data["owner"],
    )
    transition_commission(
        commission_id=commission.pk,
        agency=booking_data["agency"],
        target_status=PartnerCommission.Status.APPROVED,
    )
    payment = post_commission_payment(
        commission_id=commission.pk,
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        amount=Decimal("4000"),
        currency=booking_data["dzd"],
        exchange_rate=Decimal("1"),
        payment_method=PaymentMethod.objects.filter(is_system=True).first(),
        payment_date=date(2027, 1, 1),
    )
    assert commission.remaining_amount == Decimal("6000.0000")
    reverse_commission_payment(
        payment_id=payment.pk,
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        payment_date=date(2027, 1, 2),
        reason="Correction",
    )
    assert commission.remaining_amount == Decimal("10000.0000")
    with pytest.raises(ValidationError):
        payment.delete()


def test_partner_api_create_update_and_deactivate(booking_data):
    client = client_for(booking_data["owner"])
    created = client.post(
        reverse("partner-list"),
        {"branch": booking_data["branch"].pk, "kind": "COMPANY", "name": "API Partner"},
        format="json",
    )
    updated = client.patch(
        reverse("partner-detail", args=[created.data["id"]]),
        {"contact_name": "Agent", "is_active": False},
        format="json",
    )
    assert created.status_code == 201
    assert updated.status_code == 200
    assert updated.data["is_active"] is False


def test_trip_expense_payment_and_reversal_are_ledgered(booking_data):
    supplier = Supplier.objects.create(agency=booking_data["agency"], name="Hotel Supplier")
    expense = TripExpense.objects.create(
        agency=booking_data["agency"],
        branch=booking_data["branch"],
        trip=booking_data["trip"],
        supplier=supplier,
        category=TripExpense.Category.HOTEL,
        description="Makkah hotel contract",
        amount=Decimal("100000"),
        currency=booking_data["dzd"],
        created_by=booking_data["owner"],
    )
    payment = post_expense_payment(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        expense_id=expense.pk,
        amount=Decimal("40000"),
        currency=booking_data["dzd"],
        exchange_rate=Decimal("1"),
        payment_method=PaymentMethod.objects.filter(is_system=True).first(),
        payment_date=date(2027, 1, 1),
    )
    assert expense.remaining_amount == Decimal("60000.0000")
    reverse_expense_payment(
        agency=booking_data["agency"],
        actor=booking_data["owner"],
        payment_id=payment.pk,
        payment_date=date(2027, 1, 2),
        reason="Correction",
    )
    assert expense.remaining_amount == Decimal("100000.0000")
    with pytest.raises(ValidationError):
        payment.delete()


def test_trip_expense_api_is_trip_filtered(booking_data):
    expense = TripExpense.objects.create(
        agency=booking_data["agency"],
        branch=booking_data["branch"],
        trip=booking_data["trip"],
        category=TripExpense.Category.TRANSPORT,
        description="Coach",
        amount=Decimal("5000"),
        currency=booking_data["dzd"],
        created_by=booking_data["owner"],
    )
    response = client_for(booking_data["owner"]).get(
        reverse("trip-expense-list"), {"trip": booking_data["trip"].pk}
    )
    assert response.status_code == 200
    assert [str(item["id"]) for item in response.data["results"]] == [str(expense.pk)]


def group_draft(data, size):
    return create_booking_draft(
        agency=data["agency"], actor=data["owner"], branch=data["branch"],
        customer=data["customer"], trip=data["trip"], currency=data["dzd"],
        accounting_currency=data["dzd"], accounting_exchange_rate=Decimal("1"),
        expected_travelers=size,
    )


def group_traveler(data, booking, index, priced=True):
    link = add_inline_booking_traveler(
        booking_id=booking.pk, agency=data["agency"], actor=data["owner"],
        first_name=f"Traveler{index}", last_name="Group", birth_date=date(1990, 1, 1),
        bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
    )
    if priced:
        add_traveler_charge(
            booking_id=booking.pk, booking_traveler_id=link.pk, agency=data["agency"],
            kind=BookingTravelerCharge.Kind.ACCOMMODATION, description="Package",
            source_price=data["hotel_price"], base_amount=data["hotel_price"].amount,
            currency=data["dzd"],
        )
    return link


def test_five_person_booking_requires_all_five_validated(booking_data):
    data = booking_data
    booking = group_draft(data, 5)
    for index in range(4):
        group_traveler(data, booking, index)
    client = client_for(data["owner"])
    response = client.get(reverse("booking-detail", args=[booking.pk]))
    assert response.data["readiness"]["remaining_travelers"] == 1
    assert response.data["readiness"]["validated_travelers"] == 4
    assert response.data["readiness"]["is_ready"] is False
    with pytest.raises(ValidationError, match="all 5"):
        confirm_booking_draft(booking_id=booking.pk, agency=data["agency"])
    fifth = group_traveler(data, booking, 5, priced=False)
    with pytest.raises(ValidationError, match="Every traveler requires"):
        confirm_booking_draft(booking_id=booking.pk, agency=data["agency"])
    add_traveler_charge(
        booking_id=booking.pk, booking_traveler_id=fifth.pk, agency=data["agency"],
        kind=BookingTravelerCharge.Kind.ACCOMMODATION, description="Package",
        source_price=data["hotel_price"], base_amount=data["hotel_price"].amount,
        currency=data["dzd"],
    )
    assert confirm_booking_draft(booking_id=booking.pk, agency=data["agency"]).status == Booking.Status.CONFIRMED


def test_confirmation_rechecks_places_taken_by_another_booking(booking_data):
    data = booking_data
    data["trip"].max_travelers = 1
    data["trip"].save()
    first = group_draft(data, 1)
    second = group_draft(data, 1)
    group_traveler(data, first, 1)
    group_traveler(data, second, 2)
    confirm_booking_draft(booking_id=first.pk, agency=data["agency"])
    response = client_for(data["owner"]).get(reverse("booking-detail", args=[second.pk]))
    assert response.data["capacity"]["remaining"] == 0
    assert response.data["readiness"]["is_ready"] is False
    with pytest.raises(ValidationError, match="remaining places"):
        confirm_booking_draft(booking_id=second.pk, agency=data["agency"])
    second.refresh_from_db()
    assert second.status == Booking.Status.DRAFT


def test_booking_size_update_and_identity_validation(booking_data):
    data = booking_data
    booking = group_draft(data, 1)
    link = group_traveler(data, booking, 1)
    link.traveler.last_name = ""
    link.traveler.save()
    with pytest.raises(ValidationError, match="First and last name"):
        confirm_booking_draft(booking_id=booking.pk, agency=data["agency"])
    client = client_for(data["owner"])
    url = reverse("booking-size", args=[booking.pk])
    assert client.patch(url, {"expected_travelers": 0}, format="json").status_code == 400
    response = client.patch(url, {"expected_travelers": 5}, format="json")
    assert response.status_code == 200
    assert response.data["expected_travelers"] == 5
    assert response.data["readiness"]["remaining_travelers"] == 4
    group_traveler(data, booking, 2)
    assert client.patch(url, {"expected_travelers": 1}, format="json").status_code == 400


def test_complete_confirmed_booking_roster_without_changing_finances(booking_data):
    data = booking_data
    booking = group_draft(data, 4)
    group_traveler(data, booking, 1)
    # Reproduce a legacy booking confirmed before group-size validation existed.
    booking.refresh_from_db()
    booking.status = Booking.Status.CONFIRMED
    booking.save()
    original_total = booking.total_amount
    original_accounting_total = booking.accounting_total_amount
    client = client_for(data["owner"])
    url = reverse("booking-inline-traveler", args=[booking.pk])
    payload = {"first_name": "New", "last_name": "Traveler", "birth_date": "1990-01-01", "bed_requirement": "REQUIRED"}
    incomplete = client.post(url, {**payload, "last_name": ""}, format="json")
    assert incomplete.status_code == 400
    for remaining in [2, 1, 0]:
        response = client.post(url, payload, format="json")
        assert response.status_code == 201, response.data
        assert response.data["readiness"]["remaining_travelers"] == remaining
    assert client.post(url, payload, format="json").status_code == 400
    booking.refresh_from_db()
    assert booking.status == Booking.Status.CONFIRMED
    assert booking.total_amount == original_total
    assert booking.accounting_total_amount == original_accounting_total
    assert booking.travelers.count() == 4
    assert booking.financial_transactions.count() == 0


def test_confirmed_roster_completion_checks_capacity_and_rolls_back_person(booking_data):
    data = booking_data
    booking = group_draft(data, 2)
    group_traveler(data, booking, 1)
    booking.status = Booking.Status.CONFIRMED
    booking.save()
    data["trip"].max_travelers = 1
    data["trip"].save()
    before = Traveler.objects.count()
    with pytest.raises(ValidationError, match="remaining places"):
        add_inline_booking_traveler(
            booking_id=booking.pk, agency=data["agency"], actor=data["owner"],
            first_name="New", last_name="Traveler", birth_date=date(1990, 1, 1),
            bed_requirement=BookingTraveler.BedRequirement.REQUIRED,
        )
    assert Traveler.objects.count() == before
    assert booking.travelers.count() == 1


def flow_payload(data, room, **overrides):
    result = {
        "first_name": "Flow", "last_name": "Traveler", "birth_date": "1990-01-01", "gender": "M",
        "passport": {"first_name": "Flow", "last_name": "Traveler", "birth_date": "1990-01-01", "gender": "M", "passport_number": "FLOW123", "issue_date": "2025-01-01", "expiry_date": "2035-01-01", "nationality": str(data["country"].pk), "issuing_country": str(data["country"].pk)},
        "price_mode": "INCLUDED", "amount": "100", "rooms": [str(room.pk)],
    }
    result.update(overrides)
    return result


def flow_room(data):
    return TripAllocationRoom.objects.create(trip_hotel=data["trip_hotel"], room_type=data["room_type"], label="Flow room", standard_beds=2, extra_beds=0, created_by=data["owner"])


def test_names_only_flow_blocks_rooms_and_payments(booking_data):
    from trips.services import assign_traveler_to_room
    data = booking_data
    booking = group_draft(data, 1)
    client = client_for(data["owner"])
    response = client.post(reverse("booking-traveler-flow", args=[booking.pk]), {"names_only": True, "first_name": "Pending"}, format="json")
    assert response.status_code == 200, response.data
    assert response.data["readiness"]["payment_blockers"]
    link = booking.travelers.get()
    assert link.traveler.birth_date is None
    with pytest.raises(ValidationError, match="Complete traveler details"):
        assign_traveler_to_room(room_id=flow_room(data).pk, booking_traveler=link, agency=data["agency"], actor=data["owner"])
    with pytest.raises(ValidationError, match="Passport is required"):
        post_transaction(agency=data["agency"], actor=data["owner"], booking_id=booking.pk, kind="PAYMENT", amount=Decimal("1"), currency=data["dzd"], booking_exchange_rate=Decimal("1"), payment_method=PaymentMethod.objects.filter(is_system=True).first(), transaction_date=date(2027, 1, 1))


@pytest.mark.parametrize("mode,expected", [("INCLUDED", Decimal("1000")), ("ADDITIONAL", Decimal("1100"))])
def test_complete_traveler_flow_preserves_or_increases_total_explicitly(booking_data, mode, expected):
    data = booking_data
    booking = group_draft(data, 1)
    booking.total_amount = Decimal("1000")
    booking.accounting_total_amount = Decimal("1000")
    booking.status = Booking.Status.CONFIRMED
    booking.save()
    room = flow_room(data)
    response = client_for(data["owner"]).post(reverse("booking-traveler-flow", args=[booking.pk]), flow_payload(data, room, price_mode=mode), format="json")
    assert response.status_code == 200, response.data
    booking.refresh_from_db()
    assert booking.total_amount == expected
    assert booking.travelers.count() == 1
    assert TripRoomAssignment.objects.filter(booking_traveler__booking=booking).count() == 1
    assert response.data["readiness"]["payment_blockers"] == []
    assert booking.financial_transactions.count() == 0
    link = booking.travelers.get()
    retry = client_for(data["owner"]).post(reverse("booking-traveler-flow", args=[booking.pk]), flow_payload(data, room, link_id=str(link.pk), price_mode="EXISTING"), format="json")
    assert retry.status_code == 200, retry.data
    booking.refresh_from_db()
    assert booking.total_amount == expected
    assert link.charges.count() == 1


@pytest.mark.parametrize("failure", ["passport", "rooms", "included_total"])
def test_traveler_flow_failure_is_atomic(booking_data, failure):
    data = booking_data
    booking = group_draft(data, 1)
    booking.status = Booking.Status.CONFIRMED
    booking.total_amount = Decimal("1000")
    booking.accounting_total_amount = Decimal("1000")
    booking.save()
    payload = flow_payload(data, flow_room(data))
    if failure == "passport":
        payload["passport"]["expiry_date"] = "2025-02-01"
    elif failure == "rooms":
        payload["rooms"] = []
        payload["price_mode"] = "ADDITIONAL"
    else:
        payload["amount"] = "1001"
    before = Traveler.objects.count()
    response = client_for(data["owner"]).post(reverse("booking-traveler-flow", args=[booking.pk]), payload, format="json")
    assert response.status_code == 400, response.data
    booking.refresh_from_db()
    assert booking.total_amount == Decimal("1000")
    assert booking.travelers.count() == 0
    assert Traveler.objects.count() == before
    assert not Passport.objects.filter(passport_number="FLOW123").exists()


def test_complete_existing_name_only_traveler(booking_data):
    data = booking_data
    booking = group_draft(data, 1)
    client = client_for(data["owner"])
    url = reverse("booking-traveler-flow", args=[booking.pk])
    assert client.post(url, {"names_only": True, "first_name": "Flow"}, format="json").status_code == 200
    link = booking.travelers.get()
    response = client.post(url, flow_payload(data, flow_room(data), link_id=str(link.pk)), format="json")
    assert response.status_code == 200, response.data
    assert booking.travelers.count() == 1
    assert response.data["readiness"]["completion"][0]["issues"] == []


def prepare_payment_passports(data, booking):
    while booking.travelers.count() < booking.expected_travelers:
        person = Traveler.objects.create(agency=data["agency"], branch=data["branch"], created_by=data["owner"], first_name="Payment", last_name="Traveler", birth_date=date(1990, 1, 1))
        add_booking_traveler(booking_id=booking.pk, agency=data["agency"], traveler=person, passenger_category=data["adult"], bed_requirement="REQUIRED")
    for link in booking.travelers.all():
        if not link.traveler.passports.filter(status="CURRENT").exists():
            save_passport(traveler=link.traveler, actor=data["owner"], passport_number=f"PAY{str(link.pk).replace('-', '')[:15]}", first_name="Payment", last_name="Traveler", birth_date=date(1990, 1, 1), gender="M", nationality=data["country"], issuing_country=data["country"], issue_date=date(2025, 1, 1), expiry_date=date(2035, 1, 1))


def test_room_taken_does_not_save_traveler_or_supplement(booking_data):
    data = booking_data
    booking = group_draft(data, 2)
    booking.total_amount = booking.accounting_total_amount = Decimal("1000")
    booking.status = Booking.Status.CONFIRMED
    booking.save()
    room = flow_room(data)
    room.standard_beds = 1
    room.save()
    client = client_for(data["owner"])
    url = reverse("booking-traveler-flow", args=[booking.pk])
    assert client.post(url, flow_payload(data, room), format="json").status_code == 200
    payload = flow_payload(data, room, price_mode="ADDITIONAL")
    payload["passport"]["passport_number"] = "FLOW124"
    response = client.post(url, payload, format="json")
    assert response.status_code == 400
    booking.refresh_from_db()
    assert booking.total_amount == Decimal("1000")
    assert booking.travelers.count() == 1
    assert not Passport.objects.filter(passport_number="FLOW124").exists()


def test_invalid_passport_blocks_new_payment_but_not_refund(booking_data):
    data = booking_data
    booking = create_booking(data)
    prepare_payment_passports(data, booking)
    payment = post_payment(data, booking)
    Passport.objects.filter(traveler__booking_links__booking=booking).update(expiry_date=date(2025, 2, 1))
    with pytest.raises(ValidationError, match="Passport is not valid"):
        post_transaction(agency=data["agency"], actor=data["owner"], booking_id=booking.pk, kind="PAYMENT", amount=Decimal("1"), currency=data["dzd"], booking_exchange_rate=Decimal("1"), payment_method=payment.payment_method, transaction_date=date(2027, 1, 1))
    refund = post_transaction(agency=data["agency"], actor=data["owner"], booking_id=booking.pk, kind="REFUND", amount=Decimal("1"), currency=data["dzd"], booking_exchange_rate=Decimal("1"), payment_method=payment.payment_method, transaction_date=date(2027, 1, 1))
    assert refund.kind == "REFUND"
