from django.contrib.auth.models import Permission
from rest_framework import viewsets
from rest_framework.permissions import BasePermission, IsAuthenticated
from .access import TenantModelPermissions, delegable_permissions

from accounts.models import Role, User
from audit.services import record_event

from .serializers import (
    PermissionSerializer,
    RoleSerializer,
    UserSummarySerializer,
    UserWriteSerializer,
)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [TenantModelPermissions]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        return Role.objects.filter(agency=self.request.user.agency).prefetch_related("permissions")

    def perform_update(self, serializer):
        role = serializer.save()
        record_event(actor=self.request.user, action="role.updated", target_type="accounts.Role",
                     target_id=role.pk, request=self.request)

    def perform_create(self, serializer):
        role = serializer.save(agency=self.request.user.agency)
        record_event(
            actor=self.request.user,
            action="role.created",
            target_type="accounts.Role",
            target_id=role.pk,
            request=self.request,
        )


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    permission_classes = [TenantModelPermissions]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = User.objects.filter(agency=self.request.user.agency).select_related("branch", "agency").prefetch_related("roles")
        if self.request.user.branch_id and (
            self.request.method not in {"GET", "HEAD", "OPTIONS"}
            or not self.request.user.has_perm("accounts.view_all_users")
        ):
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset

    def perform_update(self, serializer):
        user = serializer.save()
        record_event(actor=self.request.user, action="user.updated", target_type="accounts.User",
                     target_id=user.pk, request=self.request)

    def get_serializer_class(self):
        return UserSummarySerializer if self.action in {"list", "retrieve"} else UserWriteSerializer

    def perform_create(self, serializer):
        user = serializer.save()
        record_event(
            actor=self.request.user,
            action="user.created",
            target_type="accounts.User",
            target_id=user.pk,
            request=self.request,
        )


class PermissionCatalogAccess(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.agency_id) and request.user.has_perm("accounts.view_role")


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PermissionSerializer
    permission_classes = [IsAuthenticated, PermissionCatalogAccess]
    queryset = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label", "codename"
    )

    def get_queryset(self):
        return delegable_permissions(self.request.user).order_by("content_type__app_label", "codename")
