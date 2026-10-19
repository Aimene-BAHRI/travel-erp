import pytest
from django.contrib.auth.models import Permission
from rest_framework.test import APIClient

from accounts.models import Role, User
from organizations.models import Agency, Branch


def client(user):
    result = APIClient()
    result.force_authenticate(user)
    return result


def grant(user, *codes):
    user.user_permissions.set(Permission.objects.filter(codename__in=codes))
    return User.objects.get(pk=user.pk)


@pytest.fixture
def setup(db):
    agency = Agency.objects.create(name="Access Agency", slug="access")
    foreign = Agency.objects.create(name="Foreign", slug="foreign-access")
    branch = Branch.objects.create(agency=agency, name="Branch", code="MAIN")
    other = Branch.objects.create(agency=agency, name="Other", code="OTHER")
    owner = User.objects.create_user(email="owner@access.test", agency=agency, is_superuser=True)
    member = User.objects.create_user(email="member@access.test", agency=agency, branch=branch)
    outsider = User.objects.create_user(email="foreign@access.test", agency=foreign)
    role = Role.objects.create(agency=agency, name="Trips", code="trips")
    role.permissions.add(Permission.objects.get(codename="view_trip"))
    return locals()


def test_lists_require_read_permission_and_stay_tenant_scoped(setup):
    assert client(setup["member"]).get("/api/v1/accounts/users/").status_code == 403
    result = client(setup["owner"]).get("/api/v1/accounts/users/")
    assert result.status_code == 200
    assert str(setup["outsider"].pk) not in {row["id"] for row in result.data["results"]}
    assert client(setup["owner"]).patch(
        f"/api/v1/accounts/users/{setup['outsider'].pk}/", {"is_active": False}, format="json"
    ).status_code == 404


def test_create_user_assign_role_and_show_effective_access(setup):
    result = client(setup["owner"]).post("/api/v1/accounts/users/", {
        "email": "new@access.test", "password": "Z7!Long-and-Unique-passphrase",
        "branch": str(setup["branch"].pk), "role_ids": [str(setup["role"].pk)],
    }, format="json")
    assert result.status_code == 201, result.data
    created = User.objects.get(pk=result.data["id"])
    assert created.check_password("Z7!Long-and-Unique-passphrase")
    assert created.agency_id == setup["agency"].pk
    summary = client(setup["owner"]).get(f"/api/v1/accounts/users/{created.pk}/").data
    assert "trips.view_trip" in summary["effective_permissions"]
    assert summary["role_ids"] == [str(setup["role"].pk)]


def test_role_permissions_cannot_exceed_manager_access(setup):
    manager = grant(setup["member"], "add_role", "view_role")
    manager.branch = None
    manager.save()
    permission = Permission.objects.get(codename="delete_trip")
    body = {"name": "Too powerful", "code": "powerful", "permission_ids": [permission.pk]}
    assert client(manager).post("/api/v1/accounts/roles/", body, format="json").status_code == 400
    body.update(code="agency-owner", permission_ids=[])
    assert client(manager).post("/api/v1/accounts/roles/", body, format="json").status_code == 400


def test_branch_manager_cannot_move_users_or_assign_agency_access(setup):
    manager = grant(setup["member"], "add_user", "change_user", "view_user", "view_all_users")
    body = {"email": "branch@access.test", "password": "Z7!Long-and-Unique-passphrase", "branch": None}
    assert client(manager).post("/api/v1/accounts/users/", body, format="json").status_code == 400
    body["branch"] = str(setup["other"].pk)
    assert client(manager).post("/api/v1/accounts/users/", body, format="json").status_code == 400
    body["branch"] = str(setup["branch"].pk)
    powerful = Role.objects.create(agency=setup["agency"], name="All", code="all")
    powerful.permissions.add(Permission.objects.get(codename="view_all_users"))
    body["role_ids"] = [str(powerful.pk)]
    assert client(manager).post("/api/v1/accounts/users/", body, format="json").status_code == 400
    target = User.objects.create_user(email="otherbranch@access.test", agency=setup["agency"], branch=setup["other"])
    assert client(manager).patch(f"/api/v1/accounts/users/{target.pk}/", {"branch": str(setup["branch"].pk)}, format="json").status_code == 404


def test_owner_self_and_higher_privilege_accounts_are_protected(setup):
    owner_role = Role.objects.create(agency=setup["agency"], name="Owner", code="agency-owner")
    setup["member"].roles.add(owner_role)
    api = client(setup["owner"])
    for target in [setup["owner"], setup["member"]]:
        assert api.patch(f"/api/v1/accounts/users/{target.pk}/", {"is_active": False}, format="json").status_code == 400
    assert api.patch(f"/api/v1/accounts/roles/{owner_role.pk}/", {"is_active": False}, format="json").status_code == 400


def test_foreign_branch_role_and_duplicate_role_rejected(setup):
    role = Role.objects.create(agency=setup["foreign"], name="Foreign role", code="foreign")
    body = {"email": "reject@access.test", "password": "Z7!Long-and-Unique-passphrase", "branch": str(setup["branch"].pk), "role_ids": [str(role.pk)]}
    assert client(setup["owner"]).post("/api/v1/accounts/users/", body, format="json").status_code == 400
    assert client(setup["owner"]).post("/api/v1/accounts/roles/", {"name": "Duplicate", "code": "trips"}, format="json").status_code == 400


def test_deactivate_user_and_role_updates_access(setup):
    setup["member"].roles.add(setup["role"])
    api = client(setup["owner"])
    assert api.patch(f"/api/v1/accounts/roles/{setup['role'].pk}/", {"is_active": False}, format="json").status_code == 200
    assert not User.objects.get(pk=setup["member"].pk).has_perm("trips.view_trip")
    assert api.patch(f"/api/v1/accounts/users/{setup['member'].pk}/", {"is_active": False}, format="json").status_code == 200
    result = api.get(f"/api/v1/accounts/users/{setup['member'].pk}/")
    assert result.data["effective_permissions"] == []
