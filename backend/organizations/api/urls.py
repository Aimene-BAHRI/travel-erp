from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AgencySetupView, BranchViewSet, CurrentAgencyView

router = DefaultRouter()
router.register("branches", BranchViewSet, basename="branch")

urlpatterns = [
    path("agency/", CurrentAgencyView.as_view(), name="current-agency"),
    path("setup/", AgencySetupView.as_view(), name="agency-setup"),
    *router.urls,
]
