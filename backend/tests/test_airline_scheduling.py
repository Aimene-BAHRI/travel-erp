from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from bookings.models import Booking, BookingTraveler
from finance.models import AgencyCashEntry, AirlinePricing
from notifications.models import Notification
from notifications.services import sync_notifications
from reference.models import PaymentMethod
from tests.test_airline_finance import defaults
from tests.test_bookings import booking_data as source_booking_data
from tests.test_bookings import client_for, create_booking


@pytest.fixture
def booking_data(db):
    return source_booking_data.__wrapped__(db)


def setup_airline(data):
    client = client_for(data["owner"])
    url = f"/api/v1/finance/airlines/{data['trip'].pk}/"
    assert client.put(url, defaults(), format="json").status_code == 200
    return client, url


def test_schedule_due_notification_and_payment(booking_data):
    client, url = setup_airline(booking_data)
    today = timezone.localdate()
    payload = {"amount": "1000", "due_date": str(today + timedelta(days=1))}
    response = client.post(url + "schedule-installment/", payload, format="json")
    assert response.status_code == 201, response.data
    item = response.data["installments"][0]
    assert not item["is_paid"]
    assert Decimal(response.data["paid"]) == 0
    assert not AgencyCashEntry.objects.exists()
    sync_notifications(booking_data["owner"])
    assert not Notification.objects.filter(event="AIRLINE_DUE").exists()
    payload["due_date"] = str(today - timedelta(days=1))
    assert (
        client.patch(url + f"installments/{item['id']}/", payload, format="json").status_code == 200
    )
    sync_notifications(booking_data["owner"])
    sync_notifications(booking_data["owner"])
    notes = Notification.objects.filter(event="AIRLINE_DUE", recipient=booking_data["owner"])
    assert notes.count() == 1
    assert f"trip={booking_data['trip'].pk}" in notes.get().target_url
    method = PaymentMethod.objects.get(code="cash", is_system=True)
    paid = client.post(
        url + f"installments/{item['id']}/pay/",
        {"payment_method": str(method.pk), "entry_date": str(today)},
        format="json",
    )
    assert paid.status_code == 200, paid.data
    assert Decimal(paid.data["paid"]) == 1000
    assert AgencyCashEntry.objects.count() == 1
    assert (
        client.post(url + f"installments/{item['id']}/pay/", {}, format="json").status_code == 400
    )
    sync_notifications(booking_data["owner"])
    assert notes.get().resolved_at is not None


def test_schedule_validation_delete_and_tenant_isolation(booking_data):
    client, url = setup_airline(booking_data)
    assert (
        client.post(url + "schedule-installment/", {"amount": "10"}, format="json").status_code
        == 400
    )
    payload = {"amount": "3443210", "due_date": str(timezone.localdate())}
    response = client.post(url + "schedule-installment/", payload, format="json")
    assert response.status_code == 201
    assert client.post(url + "schedule-installment/", payload, format="json").status_code == 400
    item_url = url + f"installments/{response.data['installments'][0]['id']}/"
    assert client_for(booking_data["foreign_owner"]).delete(item_url).status_code == 404
    sync_notifications(booking_data["owner"])
    assert client.delete(item_url).status_code == 200
    sync_notifications(booking_data["owner"])
    assert not Notification.objects.filter(event="AIRLINE_DUE", resolved_at__isnull=True).exists()
    assert not AgencyCashEntry.objects.exists()


def test_quantities_follow_booking_travelers_and_cancellation(booking_data):
    client, url = setup_airline(booking_data)
    booking = create_booking(booking_data)
    link = BookingTraveler.objects.create(
        booking=booking,
        traveler=booking_data["traveler"],
        passenger_category=booking_data["adult"],
        bed_requirement="REQUIRED",
    )
    result = client.get(url).data
    assert result["quantities_from_bookings"]
    assert result["rows"][0]["seats"] == 1
    assert Decimal(result["total"]) == 143210
    link.service_type = "VISA_ONLY"
    link.save()
    assert client.get(url).data["rows"][0]["seats"] == 0
    link.service_type = "PACK"
    link.save()
    booking.status = Booking.Status.CANCELLED
    booking.save()
    assert AirlinePricing.objects.get(trip=booking.trip).effective_rows[0]["seats"] == 0


def test_cash_ledger_edit_delete_and_validation(booking_data):
    data = booking_data
    client = client_for(data["owner"])
    method = PaymentMethod.objects.get(code="cash", is_system=True)
    payload = {
        "branch": str(data["branch"].pk),
        "direction": "OUT",
        "category": "TAX",
        "description": "Tax",
        "amount": "1000",
        "currency": "DZD",
        "payment_method": str(method.pk),
        "entry_date": str(timezone.localdate()),
    }
    created = client.post("/api/v1/finance/cash-entries/post/", payload, format="json")
    assert created.status_code == 201, created.data
    url = f"/api/v1/finance/cash-entries/{created.data['id']}/"
    assert client_for(data["foreign_owner"]).delete(url).status_code == 404
    assert client.patch(url, {"amount": "-1"}, format="json").status_code == 400
    assert AgencyCashEntry.objects.count() == 1
    updated = client.patch(url, {"amount": "700", "description": "Corrected tax"}, format="json")
    assert updated.status_code == 200, updated.data
    assert AgencyCashEntry.objects.count() == 3
    assert AgencyCashEntry.objects.get(pk=created.data["id"]).amount == 1000
    assert client.delete(url).status_code == 400
    report = client.get("/api/v1/finance/cash-entries/report/").data
    assert report["totals_by_currency"]["DZD"]["net"] == -700
    assert sum(row.get("editable", False) for row in report["entries"]) == 1
    assert client.delete(f"/api/v1/finance/cash-entries/{updated.data['id']}/").status_code == 204
    assert (
        client.get("/api/v1/finance/cash-entries/report/").data["totals_by_currency"]["DZD"]["net"]
        == 0
    )

@pytest.mark.parametrize("paid", [True, False])
def test_existing_installment_edit_after_flight_total_drops(booking_data, paid):
    client, url = setup_airline(booking_data)
    method = PaymentMethod.objects.get(code="cash", is_system=True)
    payload = {
        "amount": "1000000", "due_date": str(timezone.localdate()),
        "entry_date": str(timezone.localdate()), "payment_method": str(method.pk),
    }
    endpoint = "installments/" if paid else "schedule-installment/"
    first = client.post(url + endpoint, payload, format="json")
    assert first.status_code == 201, first.data
    item_id = first.data["installments"][0]["id"]
    assert client.post(url + endpoint, payload, format="json").status_code == 201
    pricing = AirlinePricing.objects.get(trip=booking_data["trip"])
    pricing.rows = [{"category": "ADULT", "seats": 1, "price": "163770"}]
    pricing.save()
    item_url = url + f"installments/{item_id}/"
    # The old form computed 163770 - 2000000 + 1000000 = -836230.
    payload["reference"] = "Corrected reference"
    unchanged = client.patch(item_url, payload, format="json")
    assert unchanged.status_code == 200, unchanged.data
    item_id = next(x["id"] for x in unchanged.data["installments"] if x["reference"] == "Corrected reference")
    item_url = url + f"installments/{item_id}/"
    payload["amount"] = "1000001"
    assert client.patch(item_url, payload, format="json").status_code == 400
    payload["amount"] = "900000"
    assert client.patch(item_url, payload, format="json").status_code == 200
