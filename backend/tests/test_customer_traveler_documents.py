from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from audit.models import AuditEvent
from documents.models import Document
from organizations.models import Agency, Branch
from reference.models import Country
from travelers.models import Passport, Traveler
from travelers.services import save_passport


@pytest.fixture
def phase_three_data(db):
    first = Agency.objects.create(name="First Travel", slug="phase-three-first")
    second = Agency.objects.create(name="Second Travel", slug="phase-three-second")
    first_branch = Branch.objects.create(agency=first, name="Oran", code="ORN")
    second_branch = Branch.objects.create(agency=second, name="Algiers", code="ALG")
    owner = User.objects.create_user(
        email="phase-three-owner@first.test",
        password="safe-test-password",
        agency=first,
        is_superuser=True,
    )
    branch_user = User.objects.create_user(
        email="phase-three-agent@first.test",
        password="safe-test-password",
        agency=first,
        branch=first_branch,
        is_superuser=True,
    )
    foreign_owner = User.objects.create_user(
        email="phase-three-owner@second.test",
        password="safe-test-password",
        agency=second,
        is_superuser=True,
    )
    country = Country.objects.create(name="Algeria", code="DZ")
    return first, second, first_branch, second_branch, owner, branch_user, foreign_owner, country


def passport_data(*, traveler, country, number, status="CURRENT"):
    return {
        "traveler": traveler,
        "status": status,
        "passport_number": number,
        "first_name": "Amina",
        "middle_name": "",
        "last_name": "Test",
        "birth_date": date(1990, 1, 1),
        "birth_place": "Oran",
        "birth_country": country,
        "nationality": country,
        "gender": "F",
        "issue_date": date(2020, 1, 1),
        "expiry_date": date(2030, 1, 1),
        "issuing_country": country,
        "issue_place": "Oran",
    }


def test_branch_user_customer_is_automatically_scoped(phase_three_data):
    first, _, first_branch, _, _, branch_user, _, _ = phase_three_data
    client = APIClient()
    client.force_authenticate(branch_user)

    response = client.post(
        reverse("customer-list"),
        {"kind": "INDIVIDUAL", "first_name": "Ahmed", "last_name": "Noui"},
        format="json",
    )

    assert response.status_code == 201
    assert str(response.data["branch"]) == str(first_branch.id)
    assert branch_user.created_customers.get().agency == first


def test_new_current_passport_replaces_previous_passport(phase_three_data):
    first, _, first_branch, _, owner, _, _, country = phase_three_data
    traveler = Traveler.objects.create(
        agency=first, branch=first_branch, created_by=owner, phone="0550000000"
    )
    first_passport = save_passport(
        actor=owner, **passport_data(traveler=traveler, country=country, number="AA 100")
    )
    second_passport = save_passport(
        actor=owner, **passport_data(traveler=traveler, country=country, number="AA200")
    )

    first_passport.refresh_from_db()
    assert first_passport.status == Passport.Status.REPLACED
    assert second_passport.status == Passport.Status.CURRENT
    assert traveler.passports.count() == 2


def test_passport_number_is_unique_per_agency_not_globally(phase_three_data):
    first, second, first_branch, second_branch, owner, _, foreign_owner, country = phase_three_data
    first_traveler = Traveler.objects.create(agency=first, branch=first_branch, created_by=owner)
    second_traveler = Traveler.objects.create(
        agency=second, branch=second_branch, created_by=foreign_owner
    )

    save_passport(
        actor=owner, **passport_data(traveler=first_traveler, country=country, number="SAME100")
    )
    save_passport(
        actor=foreign_owner,
        **passport_data(traveler=second_traveler, country=country, number="SAME100"),
    )

    assert Passport.objects.filter(passport_number="SAME100").count() == 2


def test_document_upload_is_typed_hashed_and_audited(phase_three_data, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    first, _, first_branch, _, owner, _, _, _ = phase_three_data
    traveler = Traveler.objects.create(agency=first, branch=first_branch, created_by=owner)
    client = APIClient()
    client.force_authenticate(owner)
    uploaded = SimpleUploadedFile("identity.pdf", b"test-pdf-content", "application/pdf")

    response = client.post(
        reverse("document-list"),
        {
            "file": uploaded,
            "category": "IDENTITY",
            "title": "Identity document",
            "owner_type": "TRAVELER",
            "owner_id": str(traveler.id),
        },
        format="multipart",
    )

    assert response.status_code == 201
    document = Document.objects.get(pk=response.data["id"])
    assert document.traveler_link.traveler == traveler
    assert len(document.sha256) == 64
    assert AuditEvent.objects.filter(
        action="document.uploaded", target_id=str(document.id)
    ).exists()


def test_uploaded_traveler_photo_can_be_selected_as_current(
    phase_three_data, tmp_path, settings
):
    settings.MEDIA_ROOT = tmp_path
    first, _, first_branch, _, owner, _, _, _ = phase_three_data
    traveler = Traveler.objects.create(
        agency=first, branch=first_branch, created_by=owner
    )
    client = APIClient()
    client.force_authenticate(owner)
    upload = client.post(
        reverse("document-list"),
        {
            "file": SimpleUploadedFile("face.jpg", b"jpeg-content", "image/jpeg"),
            "category": "PHOTO",
            "title": "Passport face crop",
            "owner_type": "TRAVELER",
            "owner_id": str(traveler.id),
        },
        format="multipart",
    )
    assert upload.status_code == 201

    response = client.post(
        reverse("traveler-set-current-photo", args=[traveler.id]),
        {
            "document": upload.data["id"],
            "source": "PASSPORT_AUTO_CROP",
        },
        format="json",
    )

    assert response.status_code == 200
    traveler.refresh_from_db()
    assert str(traveler.current_photo_id) == upload.data["id"]
    assert traveler.current_photo_source == "PASSPORT_AUTO_CROP"


def test_document_from_another_agency_is_not_downloadable(phase_three_data, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    first, second, first_branch, second_branch, owner, _, foreign_owner, _ = phase_three_data
    foreign_document = Document.objects.create(
        agency=second,
        branch=second_branch,
        category="OTHER",
        title="Private",
        file=SimpleUploadedFile("private.pdf", b"private", "application/pdf"),
        original_filename="private.pdf",
        mime_type="application/pdf",
        size_bytes=7,
        sha256="0" * 64,
        uploaded_by=foreign_owner,
    )
    client = APIClient()
    client.force_authenticate(owner)

    response = client.get(reverse("document-download", args=[foreign_document.id]))

    assert response.status_code == 404
    assert first != second
    assert first_branch != second_branch
