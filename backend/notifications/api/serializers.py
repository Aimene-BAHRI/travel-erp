from rest_framework import serializers

from notifications.models import Notification, NotificationRule


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "event",
            "severity",
            "title",
            "message",
            "target_url",
            "read_at",
            "resolved_at",
            "created_at",
        ]


class NotificationRuleSerializer(serializers.ModelSerializer):
    label = serializers.CharField(source="get_event_display", read_only=True)

    class Meta:
        model = NotificationRule
        fields = ["id", "event", "label", "is_enabled", "lead_days", "branch_only"]
        read_only_fields = ["id", "event", "label"]
