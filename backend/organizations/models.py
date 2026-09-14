import uuid

from django.db import models


class Agency(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=160)
    legal_name = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(max_length=80, unique=True)
    registration_number = models.CharField(max_length=100, blank=True)
    tax_number = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to="agencies/logos/", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "agencies"

    def __str__(self):
        return self.name


class AgencySettings(models.Model):
    class SetupStatus(models.TextChoices):
        SETUP = "SETUP", "Setup"
        READY = "READY", "Ready for review"
        ACTIVE = "ACTIVE", "Active"

    agency = models.OneToOneField(Agency, on_delete=models.CASCADE, related_name="settings")
    timezone = models.CharField(max_length=64, default="Africa/Algiers")
    default_language = models.CharField(max_length=10, default="en")
    setup_status = models.CharField(
        max_length=10, choices=SetupStatus.choices, default=SetupStatus.SETUP
    )
    invoice_footer = models.TextField(blank=True)
    primary_color = models.CharField(max_length=7, default="#0e7490")
    secondary_color = models.CharField(max_length=7, default="#0f172a")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "agency settings"

    def __str__(self):
        return f"Settings for {self.agency}"


class Branch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(Agency, on_delete=models.PROTECT, related_name="branches")
    name = models.CharField(max_length=160)
    code = models.CharField(max_length=30)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        permissions = [("view_all_branches", "Can view all branches in the agency")]
        constraints = [
            models.UniqueConstraint(fields=["agency", "code"], name="uniq_branch_code_agency"),
            models.UniqueConstraint(fields=["agency", "name"], name="uniq_branch_name_agency"),
        ]
        indexes = [models.Index(fields=["agency", "is_active"])]

    def __str__(self):
        return f"{self.agency.name} - {self.name}"
