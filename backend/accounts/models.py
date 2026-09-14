import uuid

from django.contrib.auth.models import AbstractUser, Permission
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .managers import UserManager


class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    agency = models.ForeignKey(
        "organizations.Agency",
        on_delete=models.CASCADE,
        related_name="roles",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    code = models.SlugField(max_length=60)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name="travel_erp_roles")
    is_system = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=Q(is_system=True, agency__isnull=True)
                | Q(is_system=False, agency__isnull=False),
                name="system_role_agency_ownership",
            ),
            models.UniqueConstraint(fields=["agency", "code"], name="uniq_role_code_agency"),
            models.UniqueConstraint(
                fields=["code"], condition=Q(is_system=True), name="uniq_system_role_code"
            ),
        ]

    def __str__(self):
        return self.name


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(unique=True)
    agency = models.ForeignKey(
        "organizations.Agency",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    branch = models.ForeignKey(
        "organizations.Branch",
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    roles = models.ManyToManyField(Role, blank=True, related_name="users")
    is_platform_admin = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        permissions = [("view_all_users", "Can view all users in the agency")]
        constraints = [
            models.CheckConstraint(
                condition=Q(is_platform_admin=True, agency__isnull=True, branch__isnull=True)
                | Q(is_platform_admin=False, agency__isnull=False),
                name="user_tenant_or_platform_admin",
            )
        ]
        indexes = [models.Index(fields=["agency", "branch", "is_active"])]

    def clean(self):
        super().clean()
        if self.branch_id and self.agency_id and self.branch.agency_id != self.agency_id:
            raise ValidationError({"branch": "The branch must belong to the user's agency."})

    def get_all_permissions(self, obj=None):
        permissions = super().get_all_permissions(obj)
        role_permissions = Permission.objects.filter(
            travel_erp_roles__users=self, travel_erp_roles__is_active=True
        )
        permissions.update(f"{p.content_type.app_label}.{p.codename}" for p in role_permissions)
        return permissions
