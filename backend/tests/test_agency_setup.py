import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Agency, AgencySettings


@pytest.mark.django_db
def test_incomplete_agency_cannot_be_activated():
    agency = Agency.objects.create(name="New Agency", slug="new-agency")
    user = User.objects.create_user(
        email="owner@new-agency.test",
        password="safe-test-password",
        agency=agency,
        is_staff=True,
    )
    client = APIClient()
    client.force_authenticate(user)

    summary = client.get(reverse("agency-setup"))
    activation = client.post(reverse("agency-setup"), {}, format="json")

    assert summary.status_code == 200
    assert summary.data["status"] == AgencySettings.SetupStatus.SETUP
    assert summary.data["complete_count"] < summary.data["total_count"]
    assert activation.status_code == 400
    assert AgencySettings.objects.get(agency=agency).setup_status == "SETUP"


@pytest.mark.django_db
def test_brand_colors_are_returned_immediately_after_update():
    agency = Agency.objects.create(name="Brand Agency", slug="brand-agency")
    AgencySettings.objects.create(agency=agency)
    user = User.objects.create_user(
        email="owner@brand-agency.test",
        password="safe-test-password",
        agency=agency,
        is_staff=True,
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.patch(
        reverse("current-agency"),
        {"settings": {"primary_color": "#112233", "secondary_color": "#445566"}},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["settings"]["primary_color"] == "#112233"
    assert response.data["settings"]["secondary_color"] == "#445566"
