from django.contrib.auth import authenticate
from django.contrib.auth.models import Permission
from rest_framework import serializers

from accounts.models import Role, User
from organizations.models import Branch


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


class UserSummarySerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    agency_name = serializers.CharField(source="agency.name", read_only=True)
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
