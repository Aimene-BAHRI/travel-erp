import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from audit.models import AuditEvent
from organizations.models import Agency


@pytest.mark.django_db
def test_login_sets_http_only_jwt_cookies_and_records_audit_event():
    agency = Agency.objects.create(name="First Travel", slug="first")
    User.objects.create_user(email="owner@first.test", password="safe-test-password", agency=agency)
    client = APIClient(enforce_csrf_checks=True)
    csrf_response = client.get(reverse("auth-csrf"))
    csrf_token = csrf_response.json()["csrfToken"]

    response = client.post(
        reverse("auth-login"),
        {"email": "owner@first.test", "password": "safe-test-password"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_token,
        HTTP_ORIGIN="http://localhost:3000",
    )

    assert response.status_code == 200
    assert response.data["email"] == "owner@first.test"
    assert response.cookies[settings.AUTH_COOKIE_ACCESS]["httponly"] is True
    assert response.cookies[settings.AUTH_COOKIE_REFRESH]["httponly"] is True
    assert response.cookies[settings.AUTH_COOKIE_ACCESS]["max-age"] == 15 * 60
    assert response.cookies[settings.AUTH_COOKIE_REFRESH]["max-age"] == 7 * 24 * 60 * 60
    assert AuditEvent.objects.filter(action="auth.login", actor__email="owner@first.test").exists()


@pytest.mark.django_db
def test_login_rejects_invalid_credentials():
    client = APIClient(enforce_csrf_checks=True)
    csrf_response = client.get(reverse("auth-csrf"))

    response = client.post(
        reverse("auth-login"),
        {"email": "missing@example.test", "password": "wrong-password"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf_response.json()["csrfToken"],
    )

    assert response.status_code == 400
