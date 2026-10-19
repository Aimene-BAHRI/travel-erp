import base64
from io import BytesIO

import pytest
from django.urls import reverse
from PIL import Image

from bookings.models import Booking
from documents.models import Document
from tests.test_bookings import booking_data as source_booking_data
from tests.test_bookings import client_for, flow_payload, flow_room, group_draft
from tests.test_passport_start import payload
from travelers.models import Passport, Traveler


@pytest.fixture
def booking_data(db, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return source_booking_data.__wrapped__(db)


def image_payload(size=(120, 80), color="white"):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return {"data": base64.b64encode(buffer.getvalue()).decode()}


def test_passport_start_stores_two_distinct_images_and_protected_links(booking_data):
    body = payload(booking_data)
    body["passport_scan"] = image_payload()
    body["photo"] = {**image_payload((32, 32), "blue"), "source": "PASSPORT_MANUAL_CROP"}
    client = client_for(booking_data["owner"])
    response = client.post(reverse("booking-passport-start"), body, format="json")
    assert response.status_code == 201, response.data
    person = Booking.objects.get(pk=response.data["id"]).travelers.get().traveler
    passport = person.passports.get()
    assert passport.passport_image_id != person.current_photo_id
    assert passport.passport_image.category == "PASSPORT"
    assert person.current_photo.category == "PHOTO"
    with passport.passport_image.file.open("rb") as stored:
        assert stored.read() == base64.b64decode(body["passport_scan"]["data"])
    result = client.get(reverse("traveler-detail", args=[person.pk]))
    scan_url = result.data["current_passport"]["passport_image_url"]
    assert str(passport.passport_image_id) in scan_url
    assert result.data["current_photo_url"] != scan_url
    path = reverse("document-download", args=[passport.passport_image_id])
    downloaded = client.get(path)
    assert downloaded.status_code == 200
    downloaded.close()
    assert client_for(booking_data["foreign_owner"]).get(path).status_code == 404
    # Returning traveler, no new uploads: keep both originals.
    again = client.post(reverse("booking-passport-start"), payload(booking_data), format="json")
    assert again.status_code == 201, again.data
    passport.refresh_from_db()
    assert passport.passport_image_id
    assert Document.objects.count() == 2


def test_group_traveler_flow_saves_scan_and_preserves_it_on_edit(booking_data):
    booking = group_draft(booking_data, 1)
    room = flow_room(booking_data)
    body = flow_payload(booking_data, room, passport_scan=image_payload())
    client = client_for(booking_data["owner"])
    url = reverse("booking-traveler-flow", args=[booking.pk])
    response = client.post(url, body, format="json")
    assert response.status_code == 200, response.data
    link = booking.travelers.get()
    passport = link.traveler.passports.get()
    image_id = passport.passport_image_id
    assert image_id
    body.pop("passport_scan")
    body.update(link_id=str(link.pk), price_mode="EXISTING")
    response = client.post(url, body, format="json")
    assert response.status_code == 200, response.data
    passport.refresh_from_db()
    assert passport.passport_image_id == image_id


@pytest.mark.parametrize("scan", [{"data": "not-base64"}, {"data": "bm90IGFuIGltYWdl"}])
def test_invalid_scan_rolls_back_booking(booking_data, scan):
    body = payload(booking_data)
    body["passport_scan"] = scan
    before = Booking.objects.count(), Traveler.objects.count(), Passport.objects.count()
    response = client_for(booking_data["owner"]).post(
        reverse("booking-passport-start"), body, format="json"
    )
    assert response.status_code == 400
    assert before == (Booking.objects.count(), Traveler.objects.count(), Passport.objects.count())
    assert not Document.objects.exists()


def test_oversized_scan_is_rejected(booking_data, settings):
    settings.MAX_DOCUMENT_SIZE_BYTES = 32
    body = payload(booking_data)
    body["passport_scan"] = image_payload()
    response = client_for(booking_data["owner"]).post(
        reverse("booking-passport-start"), body, format="json"
    )
    assert response.status_code == 400
    assert not Booking.objects.exists()
