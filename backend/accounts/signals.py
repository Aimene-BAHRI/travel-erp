from django.contrib.auth.models import Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import Role


@receiver(post_migrate)
def sync_agency_owner_permissions(sender, **kwargs):
    permissions = Permission.objects.filter(content_type__app_label=sender.label)
    if not permissions.exists():
        return
    for role in Role.objects.filter(code="agency-owner", is_system=False):
        role.permissions.add(*permissions)
