from rest_framework.routers import DefaultRouter

from .views import AllocationViewSet, CommissionPaymentViewSet, CommissionViewSet, PartnerViewSet

router = DefaultRouter()
router.register("allocations", AllocationViewSet, basename="partner-allocation")
router.register("commissions", CommissionViewSet, basename="partner-commission")
router.register("commission-payments", CommissionPaymentViewSet, basename="commission-payment")
router.register("", PartnerViewSet, basename="partner")
urlpatterns = router.urls
