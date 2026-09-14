from rest_framework.routers import DefaultRouter

from .views import (
    TripAllocationRoomViewSet,
    TripFlightViewSet,
    TripHotelViewSet,
    TripRoomAssignmentViewSet,
    TripStopViewSet,
    TripTransportViewSet,
    TripViewSet,
)

router = DefaultRouter()
router.register("stops", TripStopViewSet, basename="trip-stop")
router.register("hotels", TripHotelViewSet, basename="trip-hotel")
router.register("flights", TripFlightViewSet, basename="trip-flight")
router.register("transports", TripTransportViewSet, basename="trip-transport")
router.register("allocation-rooms", TripAllocationRoomViewSet, basename="trip-allocation-room")
router.register("room-assignments", TripRoomAssignmentViewSet, basename="trip-room-assignment")
router.register("", TripViewSet, basename="trip")

urlpatterns = router.urls
