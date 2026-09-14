from django.conf import settings
from rest_framework.authentication import CSRFCheck
from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication


def enforce_csrf(request):
    check = CSRFCheck(lambda req: None)
    check.process_request(request)
    reason = check.process_view(request, None, (), {})
    if reason:
        raise PermissionDenied(f"CSRF failed: {reason}")


class CookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        raw_token = (
            self.get_raw_token(header)
            if header
            else request.COOKIES.get(settings.AUTH_COOKIE_ACCESS)
        )
        if raw_token is None:
            return None
        validated_token = self.get_validated_token(raw_token)
        if header is None:
            enforce_csrf(request)
        return self.get_user(validated_token), validated_token
