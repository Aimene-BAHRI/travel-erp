from rest_framework.routers import DefaultRouter

from .views import AirlineViewSet, HotelViewSet, RoomTypeViewSet, RoomViewSet, SupplierViewSet

router = DefaultRouter()
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("airlines", AirlineViewSet, basename="airline")
router.register("hotels", HotelViewSet, basename="hotel")
router.register("room-types", RoomTypeViewSet, basename="room-type")
router.register("rooms", RoomViewSet, basename="room")

urlpatterns = router.urls
