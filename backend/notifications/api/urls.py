from rest_framework.routers import DefaultRouter

from .views import NotificationRuleViewSet, NotificationViewSet

router = DefaultRouter()
router.register("rules", NotificationRuleViewSet, basename="notification-rule")
router.register("", NotificationViewSet, basename="notification")
urlpatterns = router.urls
