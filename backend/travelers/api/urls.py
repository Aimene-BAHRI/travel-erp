from rest_framework.routers import DefaultRouter

from .views import PassportViewSet, TravelerViewSet

router = DefaultRouter()
router.register("passports", PassportViewSet, basename="passport")
router.register("", TravelerViewSet, basename="traveler")
urlpatterns = router.urls
