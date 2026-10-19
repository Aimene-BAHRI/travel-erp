from django.contrib.auth import authenticate
from django.contrib.auth.models import Permission
from rest_framework import serializers

from accounts.models import Role, User
from organizations.models import Branch
from .access import delegable_permissions


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"), email=attrs["email"], password=attrs["password"]
        )
        if not user or not user.is_active:
            raise serializers.ValidationError(
                "Invalid email or password.", code="invalid_credentials"
            )
        attrs["user"] = user
        return attrs


class CsrfSerializer(serializers.Serializer):
    csrfToken = serializers.CharField()


class PermissionSerializer(serializers.ModelSerializer):
    app_label = serializers.CharField(source="content_type.app_label", read_only=True)

    class Meta:
        model = Permission
        fields = ["id", "app_label", "codename", "name"]


class RoleSerializer(serializers.ModelSerializer):
    permission_ids = serializers.PrimaryKeyRelatedField(
        source="permissions", many=True, queryset=Permission.objects.all(), required=False
    )

    class Meta:
        model = Role
        fields = ["id", "name", "code", "description", "permission_ids", "is_system", "is_active"]
        read_only_fields = ["id", "is_system"]

    def validate(self, attrs):
        actor = self.context["request"].user
        if actor.branch_id:
            raise serializers.ValidationError("Agency-wide roles can only be managed by an agency-level administrator.")
        if attrs.get("code") == "agency-owner" or (self.instance and self.instance.code == "agency-owner"):
            raise serializers.ValidationError("The agency owner role is protected.")
        code = attrs.get("code", self.instance.code if self.instance else "")
        if Role.objects.filter(agency=actor.agency, code=code).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError({"code": "This role code already exists in your agency."})
        allowed = set(delegable_permissions(actor).values_list("pk", flat=True))
        if self.instance and not set(self.instance.permissions.values_list("pk", flat=True)) <= allowed:
            raise serializers.ValidationError("You cannot modify a role with access beyond your own.")
        if any(permission.pk not in allowed for permission in attrs.get("permissions", [])):
            raise serializers.ValidationError({"permission_ids": "You can only grant permissions you hold."})
        if self.instance and self.instance.users.filter(pk=actor.pk).exists():
            raise serializers.ValidationError("You cannot modify a role assigned to your own account.")
        return attrs


class UserSummarySerializer(serializers.ModelSerializer):
    role_ids = serializers.PrimaryKeyRelatedField(source="roles", many=True, read_only=True)
    effective_permissions = serializers.SerializerMethodField()
    protected_account = serializers.SerializerMethodField()

    def get_effective_permissions(self, obj):
        return sorted(obj.get_all_permissions()) if obj.is_active else []

    def get_protected_account(self, obj):
        return obj.is_superuser or obj.roles.filter(code="agency-owner", is_active=True).exists()
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    agency_name = serializers.CharField(source="agency.legal_name", read_only=True)
    role_names = serializers.SlugRelatedField(
        source="roles", many=True, read_only=True, slug_field="name"
    )

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "agency_name",
            "branch",
            "branch_name",
            "role_names",
            "role_ids",
            "effective_permissions",
            "protected_account",
            "is_active",
            "is_platform_admin",
        ]


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=10)
    role_ids = serializers.PrimaryKeyRelatedField(
        source="roles", many=True, queryset=Role.objects.none(), required=False
    )
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.none(), allow_null=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "branch",
            "role_ids",
            "password",
            "is_active",
        ]
        read_only_fields = ["id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["branch"].queryset = Branch.objects.filter(agency=request.user.agency)
            self.fields["role_ids"].queryset = Role.objects.filter(
                agency=request.user.agency, is_active=True
            )

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        roles = validated_data.pop("roles", [])
        user = User.objects.create_user(
            agency=self.context["request"].user.agency, password=password, **validated_data
        )
        user.roles.set(roles)
        return user

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "A password is required."})
        actor = self.context["request"].user
        if self.instance and (self.instance.pk == actor.pk or self.instance.is_superuser or self.instance.roles.filter(code="agency-owner", is_active=True).exists()):
            raise serializers.ValidationError("Your own account and agency owner accounts are protected here.")
        if self.instance and not self.instance.get_all_permissions() <= actor.get_all_permissions():
            raise serializers.ValidationError("You cannot modify a user with access beyond your own.")
        branch = attrs.get("branch", self.instance.branch if self.instance else None)
        if actor.branch_id and (branch is None or branch.pk != actor.branch_id):
            raise serializers.ValidationError({"branch": "Users must remain in your branch."})
        allowed = set(delegable_permissions(actor).values_list("pk", flat=True))
        for role in attrs.get("roles", []):
            if role.code == "agency-owner" or not set(role.permissions.values_list("pk", flat=True)) <= allowed:
                raise serializers.ValidationError({"role_ids": "This role grants access beyond what you can assign."})
        if attrs.get("password"):
            from django.contrib.auth.password_validation import validate_password
            from django.core.exceptions import ValidationError
            try:
                validate_password(attrs["password"], self.instance or User(email=attrs.get("email", "")))
            except ValidationError as exc:
                raise serializers.ValidationError({"password": exc.messages}) from exc
        return attrs

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        roles = validated_data.pop("roles", None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=["password"])
        if roles is not None:
            instance.roles.set(roles)
        return instance


class MeSerializer(UserSummarySerializer):
    permissions = serializers.SerializerMethodField()

    class Meta(UserSummarySerializer.Meta):
        fields = [*UserSummarySerializer.Meta.fields, "permissions"]

    def get_permissions(self, obj) -> list[str]:
        return sorted(obj.get_all_permissions())
