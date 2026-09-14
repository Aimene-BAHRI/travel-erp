from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from notifications.models import Notification, NotificationRule
from notifications.services import sync_notifications

from .serializers import NotificationRuleSerializer, NotificationSerializer


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        sync_notifications(self.request.user)
        queryset = Notification.objects.filter(recipient=self.request.user)
        view = self.request.query_params.get("view", "active")
        if view != "all":
            queryset = queryset.filter(resolved_at__isnull=True)
        if view == "unread":
            queryset = queryset.filter(read_at__isnull=True)
        return queryset

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        item = self.get_object()
        item.read_at = timezone.now()
        item.save(update_fields=["read_at"])
        return Response(self.get_serializer(item).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        Notification.objects.filter(recipient=request.user, read_at__isnull=True).update(
            read_at=timezone.now()
        )
        return Response(status=204)


class NotificationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationRuleSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        sync_notifications(self.request.user)
        return NotificationRule.objects.filter(agency=self.request.user.agency)
