from django.urls import path

from .views import (
    DashboardView,
    HealthCheckView,
    PublicBookingRequestView,
    PublicHomeView,
    PublicTripView,
)

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("public/home/", PublicHomeView.as_view(), name="public-home"),
    path("public/trips/<uuid:pk>/", PublicTripView.as_view(), name="public-trip"),
    path(
        "public/booking-requests/",
        PublicBookingRequestView.as_view(),
        name="public-booking-request",
    ),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
]
