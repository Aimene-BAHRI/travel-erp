import uuid

from django.conf import settings
from django.db import models


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, null=True, blank=True
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=80)
    target_type = models.CharField(max_length=100)
    target_id = models.CharField(max_length=100, blank=True)
    before = models.JSONField(default=dict, blank=True)
    after = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["agency", "action", "created_at"])]

    def __str__(self):
        return f"{self.action}: {self.target_type} {self.target_id}"
