from decimal import Decimal

import pytest

from finance.api.airline import CATEGORIES
from finance.models import AirlineInstallment, AirlinePricing
from finance.services import cash_flow_summary
from pricing.models import TripCostComponent
from reference.models import AgencyCurrency, Currency, PaymentMethod
from tests.test_trips import authenticated_client
from tests.test_trips import trip_data as source_trip_data


@pytest.fixture
def trip_data(db):
    return source_trip_data.__wrapped__(db)


def defaults():
    rows = [{"category": key, "seats": 0, "price": "0.00"} for key in CATEGORIES]
    rows[0].update(seats=34, price="100000.00")
    rows[3].update(seats=1, price="43210.00")
    return {"rows": rows, "visa_price": "35000.00"}


def test_airline_pricing_installments_and_cash_flow(trip_data):
    trip = trip_data["trip"]
    dzd = Currency.objects.get(code="DZD")
    AgencyCurrency.objects.create(
        agency=trip.agency, currency=dzd, is_enabled=True, is_accounting=True
    )
    trip.max_travelers = 35
    trip.save()
    client = authenticated_client(trip_data["owner"])
    url = f"/api/v1/finance/airlines/{trip.pk}/"
    response = client.put(url, defaults(), format="json")
    assert response.status_code == 200, response.data
    assert Decimal(response.data["total"]) == Decimal("3443210")
    assert TripCostComponent.objects.get(trip=trip, code="airline-visa").source_amount == Decimal(
        "35000"
    )
    method = PaymentMethod.objects.create(agency=trip.agency, code="airline-test", name="Bank")
    for amount, reference in [("1000000", "910822"), ("1000000", "911906"), ("1443210", "913511")]:
        response = client.post(
            url + "installments/",
            {
                "amount": amount,
                "reference": reference,
                "payment_method": str(method.pk),
                "entry_date": "2026-06-12",
            },
            format="json",
        )
        assert response.status_code == 201, response.data
    assert Decimal(response.data["remaining"]) == 0
    assert Decimal(response.data["progress"]) == 100
    assert AirlineInstallment.objects.count() == 3
    assert cash_flow_summary(agency=trip.agency)["totals_by_currency"]["DZD"]["outflow"] == Decimal(
        "3443210"
    )
    response = client.post(
        url + "installments/",
        {"amount": "1", "payment_method": str(method.pk), "entry_date": "2026-06-12"},
        format="json",
    )
    assert response.status_code == 400
    assert AirlineInstallment.objects.count() == 3


def test_airline_tenant_isolation_and_validation(trip_data):
    trip = trip_data["trip"]
    dzd = Currency.objects.get(code="DZD")
    AgencyCurrency.objects.create(
        agency=trip.agency, currency=dzd, is_enabled=True, is_accounting=True
    )
    trip.max_travelers = 35
    trip.save()
    url = f"/api/v1/finance/airlines/{trip.pk}/"
    foreign = authenticated_client(trip_data["foreign_owner"])
    assert foreign.get(url).status_code == 404
    assert foreign.put(url, defaults(), format="json").status_code == 404
    client = authenticated_client(trip_data["owner"])
    data = defaults()
    data["rows"][0]["seats"] = 36
    assert client.put(url, data, format="json").status_code == 400
    data = defaults()
    data["rows"][0]["price"] = "-1"
    assert client.put(url, data, format="json").status_code == 400
    data = defaults()
    data["rows"][1]["category"] = "ADULT"
    assert client.put(url, data, format="json").status_code == 400
    assert not AirlinePricing.objects.exists()


def test_airline_installment_can_be_edited_or_voided(trip_data):
    trip = trip_data["trip"]
    dzd = Currency.objects.get(code="DZD")
    AgencyCurrency.objects.create(
        agency=trip.agency, currency=dzd, is_enabled=True, is_accounting=True
    )
    client = authenticated_client(trip_data["owner"])
    url = f"/api/v1/finance/airlines/{trip.pk}/"
    assert client.put(url, defaults(), format="json").status_code == 200
    method = PaymentMethod.objects.create(agency=trip.agency, code="airline-edit", name="Bank")
    created = client.post(
        url + "installments/",
        {
            "amount": "1000000",
            "reference": "OLD",
            "payment_method": str(method.pk),
            "entry_date": "2026-06-12",
        },
        format="json",
    )
    installment_id = created.data["installments"][0]["id"]
    edited = client.patch(
        url + f"installments/{installment_id}/",
        {
            "amount": "900000",
            "reference": "UPDATED",
            "payment_method": str(method.pk),
            "entry_date": "2026-06-13",
        },
        format="json",
    )
    assert edited.status_code == 200, edited.data
    assert Decimal(edited.data["paid"]) == Decimal("900000")
    assert edited.data["installments"][0]["reference"] == "UPDATED"
    deleted = client.delete(url + f"installments/{edited.data['installments'][0]['id']}/")
    assert deleted.status_code == 200, deleted.data
    assert deleted.data["paid"] == "0"
    assert not deleted.data["installments"]
    assert AirlineInstallment.objects.filter(voided_at__isnull=False).count() == 2
