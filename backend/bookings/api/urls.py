from rest_framework.routers import DefaultRouter

from .views import BookingRequestViewSet, BookingViewSet

router = DefaultRouter()
router.register("requests", BookingRequestViewSet, basename="booking-request")
router.register("", BookingViewSet, basename="booking")

urlpatterns = router.urls
