from rest_framework.routers import DefaultRouter

from .views import (
    PromotionViewSet,
    QuoteViewSet,
    SeasonalFlightPriceViewSet,
    TripCostComponentViewSet,
    TripHotelPriceViewSet,
    TripOccupancyPackageViewSet,
)

router = DefaultRouter()
router.register("promotions", PromotionViewSet, basename="promotion")
router.register("hotel-prices", TripHotelPriceViewSet, basename="hotel-price")
router.register("flight-prices", SeasonalFlightPriceViewSet, basename="flight-price")
router.register("cost-components", TripCostComponentViewSet, basename="cost-component")
router.register("occupancy-packages", TripOccupancyPackageViewSet, basename="occupancy-package")
router.register("quotes", QuoteViewSet, basename="quote")

urlpatterns = router.urls
