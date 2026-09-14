import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Agency
from reference.models import AgencyCurrency, Country, Currency, PassengerCategory, PaymentMethod


@pytest.fixture
def reference_tenants(db):
    first = Agency.objects.create(name="First Travel", slug="reference-first")
    second = Agency.objects.create(name="Second Travel", slug="reference-second")
    user = User.objects.create_user(
        email="reference-owner@first.test",
        password="safe-test-password",
        agency=first,
        is_superuser=True,
    )
    return first, second, user


def test_required_system_reference_data_is_seeded(db):
    assert set(Currency.objects.values_list("code", flat=True)) >= {"DZD", "EUR", "SAR", "USD"}
    assert set(PassengerCategory.objects.filter(is_system=True).values_list("code", flat=True)) >= {
        "adt",
        "chd",
        "inf",
        "guide",
    }


def test_country_code_is_normalized(db):
    country = Country.objects.create(name="Algeria", code="dz")

    assert country.code == "DZ"


def test_custom_payment_method_is_scoped_to_creating_agency(reference_tenants):
    first, second, user = reference_tenants
    foreign_method = PaymentMethod.objects.create(
        agency=second, code="foreign-method", name="Foreign Method", is_system=False
    )
    client = APIClient()
    client.force_authenticate(user)

    create_response = client.post(
        reverse("payment-method-list"), {"code": "voucher", "name": "Voucher"}, format="json"
    )
    list_response = client.get(reverse("payment-method-list"))

    assert create_response.status_code == 201
    assert PaymentMethod.objects.get(pk=create_response.data["id"]).agency == first
    returned_ids = {item["id"] for item in list_response.data["results"]}
    assert str(foreign_method.id) not in returned_ids


def test_system_payment_method_cannot_be_modified(reference_tenants):
    _, _, user = reference_tenants
    method = PaymentMethod.objects.get(code="cash", is_system=True)
    client = APIClient()
    client.force_authenticate(user)

    response = client.patch(
        reverse("payment-method-detail", args=[method.id]), {"name": "Changed"}, format="json"
    )

    assert response.status_code == 403


def test_only_one_accounting_currency_per_agency(reference_tenants):
    first, _, user = reference_tenants
    dzd = Currency.objects.get(code="DZD")
    eur = Currency.objects.get(code="EUR")
    AgencyCurrency.objects.create(agency=first, currency=dzd, is_enabled=True, is_accounting=True)
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        reverse("agency-currency-list"),
        {"currency": eur.code, "is_enabled": True, "is_accounting": True},
        format="json",
    )

    assert response.status_code == 400
    assert AgencyCurrency.objects.filter(agency=first, is_accounting=True).count() == 1


def test_accounting_currency_switch_is_atomic(reference_tenants):
    first, _, user = reference_tenants
    dzd = AgencyCurrency.objects.create(
        agency=first,
        currency=Currency.objects.get(code="DZD"),
        is_enabled=True,
        is_accounting=True,
    )
    eur = AgencyCurrency.objects.create(
        agency=first,
        currency=Currency.objects.get(code="EUR"),
        is_enabled=False,
        is_accounting=False,
    )
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(reverse("agency-currency-make-accounting", args=[eur.id]))

    assert response.status_code == 200
    dzd.refresh_from_db()
    eur.refresh_from_db()
    assert dzd.is_accounting is False
    assert eur.is_accounting is True
    assert eur.is_enabled is True
