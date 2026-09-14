import uuid
from pathlib import Path

from django.conf import settings
from django.db import models


def document_upload_path(instance, filename):
    safe_name = Path(filename).name
    return f"agencies/{instance.agency_id}/documents/{instance.id}/{safe_name}"


class Document(models.Model):
    class Category(models.TextChoices):
        PASSPORT = "PASSPORT", "Passport"
        PHOTO = "PHOTO", "Photo"
        IDENTITY = "IDENTITY", "Identity"
        VISA = "VISA", "Visa"
        CONTRACT = "CONTRACT", "Contract"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="documents"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="documents"
    )
    category = models.CharField(max_length=20, choices=Category.choices)
    title = models.CharField(max_length=180)
    file = models.FileField(upload_to=document_upload_path, max_length=500)
    original_filename = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=120)
    size_bytes = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("view_all_documents", "Can view all documents in the agency")]
        indexes = [models.Index(fields=["agency", "branch", "category"])]

    def __str__(self):
        return self.title
