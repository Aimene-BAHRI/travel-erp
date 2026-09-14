from contextlib import suppress

from django.conf import settings
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.authentication import enforce_csrf
from audit.services import record_event

from .serializers import CsrfSerializer, LoginSerializer, MeSerializer


def set_auth_cookies(response, refresh):
    cookie_options = {
        "httponly": True,
        "secure": settings.AUTH_COOKIE_SECURE,
        "samesite": settings.AUTH_COOKIE_SAMESITE,
        "path": settings.AUTH_COOKIE_PATH,
    }
    response.set_cookie(
        settings.AUTH_COOKIE_ACCESS,
        str(refresh.access_token),
        max_age=int(settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"].total_seconds()),
        **cookie_options,
    )
    response.set_cookie(
        settings.AUTH_COOKIE_REFRESH,
        str(refresh),
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        **cookie_options,
    )


class CsrfView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: CsrfSerializer}, auth=[])
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=LoginSerializer, responses={200: MeSerializer}, auth=[])
    def post(self, request):
        enforce_csrf(request)
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)
        response = Response(MeSerializer(user).data)
        set_auth_cookies(response, refresh)
        record_event(
            actor=user,
            action="auth.login",
            target_type="accounts.User",
            target_id=user.pk,
            request=request,
        )
        return response


class RefreshView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=None, responses={204: None}, auth=[])
    def post(self, request):
        enforce_csrf(request)
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if not raw_refresh:
            return Response(
                {"detail": "Refresh token is missing."}, status=status.HTTP_401_UNAUTHORIZED
            )
        try:
            old_refresh = RefreshToken(raw_refresh)
            user_id = old_refresh["user_id"]
            old_refresh.blacklist()
            from accounts.models import User

            user = User.objects.get(pk=user_id, is_active=True)
            refresh = RefreshToken.for_user(user)
        except (TokenError, User.DoesNotExist):
            return Response(
                {"detail": "Refresh token is invalid."}, status=status.HTTP_401_UNAUTHORIZED
            )
        response = Response(status=status.HTTP_204_NO_CONTENT)
        set_auth_cookies(response, refresh)
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if raw_refresh:
            with suppress(TokenError):
                RefreshToken(raw_refresh).blacklist()
        record_event(
            actor=request.user,
            action="auth.logout",
            target_type="accounts.User",
            target_id=request.user.pk,
            request=request,
        )
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(settings.AUTH_COOKIE_ACCESS, path=settings.AUTH_COOKIE_PATH)
        response.delete_cookie(settings.AUTH_COOKIE_REFRESH, path=settings.AUTH_COOKIE_PATH)
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MeSerializer})
    def get(self, request):
        return Response(MeSerializer(request.user).data)
