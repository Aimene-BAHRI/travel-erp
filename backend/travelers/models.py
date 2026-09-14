import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Traveler(models.Model):
    class Gender(models.TextChoices):
        FEMALE = "F", "Female"
        MALE = "M", "Male"
        UNSPECIFIED = "X", "Unspecified"

    class PhotoSource(models.TextChoices):
        PASSPORT_AUTO_CROP = "PASSPORT_AUTO_CROP", "Passport automatic crop"
        PASSPORT_MANUAL_CROP = "PASSPORT_MANUAL_CROP", "Passport manual crop"
        MANUAL_UPLOAD = "MANUAL_UPLOAD", "Manual upload"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="travelers"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="travelers"
    )
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, default=Gender.UNSPECIFIED)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    current_photo = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="traveler_current_photo_for",
    )
    current_photo_source = models.CharField(max_length=24, choices=PhotoSource.choices, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_travelers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("view_all_travelers", "Can view all travelers in the agency")]
        indexes = [models.Index(fields=["agency", "branch", "is_active"])]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        name = f"{self.first_name} {self.last_name}".strip()
        if name:
            return name
        current_passport = next(
            (passport for passport in self.passports.all() if passport.status == "CURRENT"),
            None,
        )
        if current_passport:
            return f"{current_passport.first_name} {current_passport.last_name}".strip()
        return self.phone or self.email or f"Traveler {self.pk}"

    def clean(self):
        super().clean()
        if self.current_photo_id and self.current_photo.agency_id != self.agency_id:
            raise ValidationError({"current_photo": "The photo must belong to the same agency."})


class Passport(models.Model):
    class Status(models.TextChoices):
        CURRENT = "CURRENT", "Current"
        EXPIRED = "EXPIRED", "Expired"
        REPLACED = "REPLACED", "Replaced"

    class Gender(models.TextChoices):
        FEMALE = "F", "Female"
        MALE = "M", "Male"
        UNSPECIFIED = "X", "Unspecified"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="passports"
    )
    traveler = models.ForeignKey(Traveler, on_delete=models.PROTECT, related_name="passports")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CURRENT)
    passport_number = models.CharField(max_length=40)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    birth_date = models.DateField()
    birth_place = models.CharField(max_length=140, blank=True)
    birth_country = models.ForeignKey(
        "reference.Country",
        on_delete=models.PROTECT,
        related_name="passport_births",
        null=True,
        blank=True,
    )
    nationality = models.ForeignKey(
        "reference.Country", on_delete=models.PROTECT, related_name="passport_nationals"
    )
    gender = models.CharField(max_length=1, choices=Gender.choices)
    issue_date = models.DateField()
    expiry_date = models.DateField()
    issuing_country = models.ForeignKey(
        "reference.Country", on_delete=models.PROTECT, related_name="issued_passports"
    )
    issue_place = models.CharField(max_length=140, blank=True)
    mrz = models.TextField(blank=True)
    passport_image = models.ForeignKey(
        "documents.Document",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="passport_image_for",
    )
    ocr_raw_data = models.JSONField(default=dict, blank=True)
    ocr_source = models.CharField(max_length=80, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_passports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-issue_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["agency", "passport_number"], name="uniq_passport_number_agency"
            ),
            models.UniqueConstraint(
                fields=["traveler"],
                condition=Q(status="CURRENT"),
                name="uniq_current_passport_traveler",
            ),
            models.CheckConstraint(
                condition=Q(expiry_date__gte=F("issue_date")),
                name="passport_expiry_on_or_after_issue",
            ),
        ]
        indexes = [
            models.Index(fields=["agency", "passport_number"]),
            models.Index(fields=["agency", "last_name", "first_name"]),
            models.Index(fields=["traveler", "status"]),
        ]

    def __str__(self):
        return f"{self.passport_number} - {self.first_name} {self.last_name}"

    def save(self, *args, **kwargs):
        self.passport_number = self.passport_number.upper().replace(" ", "")
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        self.passport_number = self.passport_number.upper().replace(" ", "")
        if self.traveler_id and self.traveler.agency_id != self.agency_id:
            raise ValidationError({"traveler": "The traveler must belong to the same agency."})
        if self.passport_image_id and self.passport_image.agency_id != self.agency_id:
            raise ValidationError({"passport_image": "The image must belong to the same agency."})


class TravelerDocument(models.Model):
    traveler = models.ForeignKey(Traveler, on_delete=models.CASCADE, related_name="document_links")
    document = models.OneToOneField(
        "documents.Document", on_delete=models.CASCADE, related_name="traveler_link"
    )
    purpose = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"{self.traveler_id}: {self.document.title}"


class PassportDocument(models.Model):
    passport = models.ForeignKey(Passport, on_delete=models.CASCADE, related_name="document_links")
    document = models.OneToOneField(
        "documents.Document", on_delete=models.CASCADE, related_name="passport_link"
    )
    purpose = models.CharField(max_length=80, blank=True)

    def __str__(self):
        return f"{self.passport_id}: {self.document.title}"
