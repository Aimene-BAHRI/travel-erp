from drf_spectacular.extensions import OpenApiAuthenticationExtension


class CookieJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "accounts.authentication.CookieJWTAuthentication"
    name = "cookieJwtAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": "travel_erp_access",
            "description": "JWT access token stored in an HTTP-only cookie.",
        }
