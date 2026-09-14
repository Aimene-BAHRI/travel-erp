from django.contrib.auth.models import Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from accounts.models import Role


@receiver(post_migrate)
def sync_agency_owner_permissions(sender, **kwargs):
    if sender.name != "reference":
        return
    permissions = Permission.objects.filter(content_type__app_label="reference")
    for role in Role.objects.filter(code="agency-owner", is_system=False):
        role.permissions.add(*permissions)
