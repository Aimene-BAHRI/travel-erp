import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class Customer(models.Model):
    class Kind(models.TextChoices):
        INDIVIDUAL = "INDIVIDUAL", "Individual"
        COMPANY = "COMPANY", "Company"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency", on_delete=models.PROTECT, related_name="customers"
    )
    branch = models.ForeignKey(
        "organizations.Branch", on_delete=models.PROTECT, related_name="customers"
    )
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.INDIVIDUAL)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=180, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_customers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name", "company_name"]
        permissions = [("view_all_customers", "Can view all customers in the agency")]
        constraints = [
            models.CheckConstraint(
                condition=Q(kind="COMPANY", company_name__gt="")
                | Q(kind="INDIVIDUAL") & (Q(first_name__gt="") | Q(last_name__gt="")),
                name="customer_required_name",
            )
        ]
        indexes = [
            models.Index(fields=["agency", "branch", "is_active"]),
            models.Index(fields=["agency", "last_name", "first_name"]),
        ]

    def __str__(self):
        return self.display_name

    @property
    def display_name(self):
        if self.kind == self.Kind.COMPANY:
            return self.company_name
        return " ".join(part for part in [self.first_name, self.last_name] if part)
