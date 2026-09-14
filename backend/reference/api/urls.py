from rest_framework.routers import DefaultRouter

from .views import (
    AgencyCurrencyViewSet,
    CityViewSet,
    CountryViewSet,
    CurrencyViewSet,
    PassengerCategoryViewSet,
    PaymentMethodViewSet,
)

router = DefaultRouter()
router.register("countries", CountryViewSet, basename="country")
router.register("cities", CityViewSet, basename="city")
router.register("currencies", CurrencyViewSet, basename="currency")
router.register("agency-currencies", AgencyCurrencyViewSet, basename="agency-currency")
router.register("passenger-categories", PassengerCategoryViewSet, basename="passenger-category")
router.register("payment-methods", PaymentMethodViewSet, basename="payment-method")

urlpatterns = router.urls
