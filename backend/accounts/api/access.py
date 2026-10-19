from django.contrib.auth.models import Permission
from django.db.models import Q
from rest_framework.permissions import DjangoModelPermissions


class TenantModelPermissions(DjangoModelPermissions):
    perms_map = {**DjangoModelPermissions.perms_map, "GET": ["%(app_label)s.view_%(model_name)s"]}

    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.agency_id) and super().has_permission(request, view)


def delegable_permissions(user):
    keys = user.get_all_permissions()
    query = Q(pk__in=[])
    for key in keys:
        app, code = key.split(".", 1)
        if user.branch_id and (code.startswith("view_all_") or app == "accounts"):
            continue
        query |= Q(content_type__app_label=app, codename=code)
    return Permission.objects.filter(query).select_related("content_type")
