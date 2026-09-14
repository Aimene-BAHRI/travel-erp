import pytest
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Role, User
from organizations.models import Agency, Branch


@pytest.fixture
def agencies(db):
    first = Agency.objects.create(name="First Travel", slug="first")
    second = Agency.objects.create(name="Second Travel", slug="second")
    return first, second


@pytest.fixture
def tenant_data(agencies):
    first, second = agencies
    first_branch = Branch.objects.create(agency=first, name="Oran", code="ORN")
    second_branch = Branch.objects.create(agency=second, name="Algiers", code="ALG")
    user = User.objects.create_user(
        email="owner@first.test",
        password="safe-test-password",
        agency=first,
        is_staff=True,
        is_superuser=True,
    )
    return user, first_branch, second_branch


def test_user_rejects_branch_from_another_agency(agencies):
    first, second = agencies
    foreign_branch = Branch.objects.create(agency=second, name="Algiers", code="ALG")
    user = User(email="user@first.test", agency=first, branch=foreign_branch)

    with pytest.raises(ValidationError):
        user.full_clean()


def test_branch_api_never_returns_another_agency(tenant_data):
    user, own_branch, foreign_branch = tenant_data
    client = APIClient()
    client.force_authenticate(user)

    response = client.get(reverse("branch-list"))

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["results"]}
    assert str(own_branch.id) in ids
    assert str(foreign_branch.id) not in ids


def test_branch_detail_hides_foreign_agency(tenant_data):
    user, _, foreign_branch = tenant_data
    client = APIClient()
    client.force_authenticate(user)

    response = client.get(reverse("branch-detail", args=[foreign_branch.id]))

    assert response.status_code == 404


def test_platform_admin_has_no_agency_or_branch(db):
    user = User.objects.create_superuser("platform@example.test", "safe-test-password")

    assert user.is_platform_admin is True
    assert user.agency_id is None
    assert user.branch_id is None


def test_agency_role_grants_permission(agencies):
    first, _ = agencies
    user = User.objects.create_user(
        email="agent@first.test", password="safe-test-password", agency=first
    )
    permission = Permission.objects.get(codename="view_branch")
    role = Role.objects.create(agency=first, name="Branch Viewer", code="branch-viewer")
    role.permissions.add(permission)
    user.roles.add(role)

    assert user.has_perm("organizations.view_branch") is True
