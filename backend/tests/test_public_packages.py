from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from bookings.models import Booking, BookingRequest
from organizations.models import Agency, Branch
from pricing.calculator import calculate_package
from pricing.models import TripCostComponent, TripOccupancyPackage
from reference.models import AgencyCurrency, Currency
from trips.models import Trip


@pytest.fixture
def package_data(db, settings, tmp_path):
    cache.clear()
    settings.PRIVATE_PASSPORT_ROOT = tmp_path / "private"
    settings.MEDIA_ROOT = tmp_path / "public"
    agency = Agency.objects.create(name="Example", slug="example")
    branch = Branch.objects.create(agency=agency, name="Main", code="MAIN")
    owner = User.objects.create_user(email="example@test.local", agency=agency, is_superuser=True)
    trip = Trip.objects.create(
        agency=agency,
        branch=branch,
        name="Example trip",
        code="EXAMPLE",
        created_by=owner,
        departure_date=timezone.localdate() + timedelta(days=30),
        return_date=timezone.localdate() + timedelta(days=44),
        status="OPEN",
    )
    dzd = Currency.objects.get(pk="DZD")
    sar = Currency.objects.get(pk="SAR")
    AgencyCurrency.objects.create(agency=agency, currency=dzd, is_enabled=True, is_accounting=True)
    AgencyCurrency.objects.create(agency=agency, currency=sar, is_enabled=True)
    for code, basis, amount, quantity, currency, rate in [
        ("makkah", "MAKKAH_ROOM", "370", "11", sar, "66"),
        ("madinah", "MADINAH_ROOM", "350", "3", sar, "66"),
        ("flight", "PER_TRAVELER", "115000", "1", dzd, "1"),
        ("fees", "PER_TRAVELER", "48000", "1", dzd, "1"),
    ]:
        TripCostComponent.objects.create(
            agency=agency,
            trip=trip,
            code=code,
            label=code,
            basis=basis,
            source_amount=Decimal(amount),
            quantity=Decimal(quantity),
            source_currency=currency,
            exchange_rate=Decimal(rate),
        )
    package = TripOccupancyPackage.objects.create(
        agency=agency,
        trip=trip,
        code="quad",
        name="Quad",
        makkah_occupancy=4,
        madinah_occupancy=4,
        margin_adult=Decimal("35000"),
        override_child_no_bed=Decimal("155000"),
        override_infant=Decimal("85000"),
        rounding_increment=1,
        is_published=True,
    )
    return agency, branch, owner, trip, package


def test_sheet_examples(package_data):
    _, _, _, _, package = package_data
    for makkah, madinah, margin, expected in [
        (1, 1, "30000", "530920"),
        (2, 2, "50000", "381960"),
        (3, 3, "40000", "315640"),
        (4, 4, "35000", "282480"),
        (5, 4, "30000", "264049"),
    ]:
        package.makkah_occupancy = makkah
        package.madinah_occupancy = madinah
        package.margin_adult = Decimal(margin)
        result = calculate_package(package, {"adult": 2, "child_no_bed": 1, "infant": 1})
        assert Decimal(result["unit_prices"]["adult"]) == Decimal(expected)
        assert Decimal(result["total"]) == 2 * Decimal(expected) + 240000


def test_rounding_and_explicit_override(package_data):
    package = package_data[-1]
    package.rounding_increment = 1000
    assert calculate_package(package)["unit_prices"]["adult"] == "283000"
    package.override_adult = Decimal("269125.5000")
    assert calculate_package(package)["unit_prices"]["adult"] == "269125.5000"


def payload(trip, package):
    return {
        "trip": str(trip.pk),
        "package": str(package.pk),
        "customer_name": "Test request",
        "phone": "0000000000",
        "adults": 2,
        "children_without_bed": 1,
        "infants": 1,
        "consent": True,
    }


def test_public_prices_and_saved_total_ignore_tampering(package_data):
    _, _, owner, trip, package = package_data
    client = APIClient()
    detail = client.get(f"/api/v1/public/trips/{trip.pk}/")
    assert detail.status_code == 200
    public = detail.data["packages"][0]
    assert "breakdown" not in public
    assert "margin" not in str(public)
    data = payload(trip, package) | {"calculated_total": "1", "pricing_snapshot": {"total": "1"}}
    response = client.post("/api/v1/public/booking-requests/", data, format="json")
    assert response.status_code == 201, response.data
    lead = BookingRequest.objects.get(reference=response.data["reference"])
    assert lead.calculated_total == Decimal("804960")
    package.override_adult = Decimal("999999")
    package.save()
    lead.refresh_from_db()
    assert lead.calculated_total == Decimal("804960")
    client.force_authenticate(owner)
    inbox = client.get("/api/v1/bookings/requests/")
    assert inbox.data["results"][0]["calculated_total"] == "804960.0000"


def test_public_request_rejects_stale_expected_total(package_data):
    _, _, _, trip, package = package_data
    response = APIClient().post(
        "/api/v1/public/booking-requests/",
        payload(trip, package) | {"expected_total": "1.0000"},
        format="json",
    )
    assert response.status_code == 409
    assert "prices changed" in response.data["detail"].lower()
    assert not BookingRequest.objects.exists()


def test_invalid_unpublished_foreign_and_fractional_input(package_data):
    _, _, _, trip, package = package_data
    client = APIClient()
    for update in [{"trip": "bad"}, {"package": "bad"}, {"adults": 1.5}, {"consent": False}]:
        assert (
            client.post(
                "/api/v1/public/booking-requests/", payload(trip, package) | update, format="json"
            ).status_code
            == 400
        )
    package.is_published = False
    package.save()
    assert (
        client.post(
            "/api/v1/public/booking-requests/", payload(trip, package), format="json"
        ).status_code
        == 400
    )
    assert not BookingRequest.objects.exists()


def test_passport_upload_requires_explicit_passport_consent(package_data):
    _, _, _, trip, package = package_data
    stream = BytesIO()
    Image.new("RGB", (16, 16), "white").save(stream, format="PNG")
    upload = SimpleUploadedFile("passport.png", stream.getvalue(), content_type="image/png")
    response = APIClient().post(
        "/api/v1/public/booking-requests/",
        payload(trip, package) | {"passports": [upload]},
        format="multipart",
    )
    assert response.status_code == 400
    assert "passport" in str(response.data).lower()
    assert not BookingRequest.objects.exists()


def test_private_passport_and_tenant_scope(package_data, settings):
    _, _, owner, trip, package = package_data
    client = APIClient()
    stream = BytesIO()
    Image.new("RGB", (16, 16), "white").save(stream, format="PNG")
    upload = SimpleUploadedFile("passport.png", stream.getvalue(), content_type="image/png")
    data = payload(trip, package) | {"passports": [upload], "passport_consent": True}
    response = client.post("/api/v1/public/booking-requests/", data, format="multipart")
    assert response.status_code == 201, response.data
    lead = BookingRequest.objects.get(reference=response.data["reference"])
    attachment = lead.attachments.get()
    assert Path(attachment.file.path).is_relative_to(settings.PRIVATE_PASSPORT_ROOT)
    assert not Path(attachment.file.path).is_relative_to(settings.MEDIA_ROOT)
    with pytest.raises(ValueError):
        _ = attachment.file.url
    path = f"/api/v1/bookings/requests/{lead.pk}/attachments/{attachment.pk}/download/"
    assert client.get(path).status_code == 401
    foreign = Agency.objects.create(name="Foreign", slug="foreign")
    other = User.objects.create_user(email="other@test.local", agency=foreign, is_superuser=True)
    client.force_authenticate(other)
    assert client.get(path).status_code == 404
    client.force_authenticate(owner)
    downloaded = client.get(path)
    assert downloaded.status_code == 200
    assert downloaded["Cache-Control"] == "private, no-store"
    assert b"".join(downloaded.streaming_content) == stream.getvalue()


def test_fake_image_rejected(package_data):
    _, _, _, trip, package = package_data
    fake = SimpleUploadedFile("passport.png", b"<script>bad</script>", content_type="image/png")
    response = APIClient().post(
        "/api/v1/public/booking-requests/",
        payload(trip, package) | {"passports": [fake], "passport_consent": True},
        format="multipart",
    )
    assert response.status_code == 400
    assert not BookingRequest.objects.exists()


def test_component_api_validates_model(package_data):
    _, _, owner, trip, _ = package_data
    client = APIClient()
    client.force_authenticate(owner)
    response = client.post(
        "/api/v1/pricing/cost-components/",
        {
            "trip": str(trip.pk),
            "code": "invalid",
            "label": "Invalid rate",
            "source_amount": "10",
            "source_currency": "DZD",
            "exchange_rate": "0",
            "quantity": "1",
        },
        format="json",
    )
    assert response.status_code == 400


def test_booking_request_converts_to_idempotent_draft(package_data):
    _, _, owner, trip, package = package_data
    client = APIClient()
    response = client.post(
        "/api/v1/public/booking-requests/", payload(trip, package), format="json"
    )
    assert response.status_code == 201, response.data
    lead = BookingRequest.objects.get(reference=response.data["reference"])

    client.force_authenticate(owner)
    converted = client.post(f"/api/v1/bookings/requests/{lead.pk}/convert/")
    assert converted.status_code == 200, converted.data
    booking = Booking.objects.get(pk=converted.data["id"])
    assert booking.expected_travelers == lead.adults + lead.children + lead.infants
    assert booking.status == Booking.Status.DRAFT
    assert booking.branch_id == trip.branch_id
    assert booking.currency_id == lead.calculated_currency_id
    assert booking.customer.first_name == "Test"
    assert booking.customer.last_name == "request"
    lead.refresh_from_db()
    assert lead.status == BookingRequest.Status.CONVERTED
    assert lead.booking_id == booking.pk
    assert lead.reference in booking.notes
    assert "804960" in booking.notes

    retry = client.post(f"/api/v1/bookings/requests/{lead.pk}/convert/")
    assert retry.status_code == 200
    assert retry.data["id"] == str(booking.pk)
    assert Booking.objects.filter(pk=booking.pk).count() == 1


def test_booking_request_cannot_be_manually_marked_converted(package_data):
    _, _, owner, trip, package = package_data
    client = APIClient()
    response = client.post(
        "/api/v1/public/booking-requests/", payload(trip, package), format="json"
    )
    lead = BookingRequest.objects.get(reference=response.data["reference"])
    client.force_authenticate(owner)
    blocked = client.patch(
        f"/api/v1/bookings/requests/{lead.pk}/",
        {"status": BookingRequest.Status.CONVERTED},
        format="json",
    )
    assert blocked.status_code == 400
    lead.refresh_from_db()
    assert lead.status != BookingRequest.Status.CONVERTED


def test_trip_capacity_exposes_remaining_places_and_blocks_over_capacity(package_data):
    _, _, _, trip, package = package_data
    trip.max_travelers = 3
    trip.save(update_fields=["max_travelers"])
    client = APIClient()
    detail = client.get(f"/api/v1/public/trips/{trip.pk}/")
    assert detail.status_code == 200
    assert detail.data["max_travelers"] == 3
    assert detail.data["booked_places"] == 0
    assert detail.data["remaining_places"] == 3

    requested = payload(trip, package)
    requested["adults"] = 3
    response = client.post(
        "/api/v1/public/booking-requests/", requested, format="json"
    )
    assert response.status_code == 409
    assert "remaining places" in response.data["detail"]
