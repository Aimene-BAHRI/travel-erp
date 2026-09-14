from django.contrib.auth.models import Permission
from rest_framework import viewsets
from rest_framework.permissions import DjangoModelPermissions

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
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        return Role.objects.filter(agency=self.request.user.agency)

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
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        queryset = User.objects.filter(agency=self.request.user.agency)
        if self.request.user.branch_id and not self.request.user.has_perm(
            "accounts.view_all_users"
        ):
            queryset = queryset.filter(branch=self.request.user.branch)
        return queryset

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


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PermissionSerializer
    permission_classes = [DjangoModelPermissions]
    queryset = Permission.objects.select_related("content_type").order_by(
        "content_type__app_label", "codename"
    )
