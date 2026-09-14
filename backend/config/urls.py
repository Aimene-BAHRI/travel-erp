from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("common.api.urls")),
    path("api/v1/auth/", include("accounts.api.auth_urls")),
    path("api/v1/accounts/", include("accounts.api.urls")),
    path("api/v1/organizations/", include("organizations.api.urls")),
    path("api/v1/reference/", include("reference.api.urls")),
    path("api/v1/customers/", include("customers.api.urls")),
    path("api/v1/travelers/", include("travelers.api.urls")),
    path("api/v1/documents/", include("documents.api.urls")),
    path("api/v1/catalog/", include("catalog.api.urls")),
    path("api/v1/trips/", include("trips.api.urls")),
    path("api/v1/pricing/", include("pricing.api.urls")),
    path("api/v1/bookings/", include("bookings.api.urls")),
    path("api/v1/finance/", include("finance.api.urls")),
    path("api/v1/partners/", include("partners.api.urls")),
    path("api/v1/notifications/", include("notifications.api.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
