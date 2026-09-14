from rest_framework import serializers

from organizations.models import Agency, AgencySettings, Branch


class AgencySettingsSerializer(serializers.ModelSerializer):
    primary_color = serializers.RegexField(regex=r"^#[0-9a-fA-F]{6}$")
    secondary_color = serializers.RegexField(regex=r"^#[0-9a-fA-F]{6}$")

    class Meta:
        model = AgencySettings
        fields = [
            "timezone",
            "default_language",
            "setup_status",
            "invoice_footer",
            "primary_color",
            "secondary_color",
        ]
        read_only_fields = ["setup_status"]


class AgencySerializer(serializers.ModelSerializer):
    settings = AgencySettingsSerializer(read_only=True)

    class Meta:
        model = Agency
        fields = [
            "id",
            "name",
            "legal_name",
            "slug",
            "registration_number",
            "tax_number",
            "address",
            "phone",
            "email",
            "website",
            "logo",
            "is_active",
            "settings",
        ]
        read_only_fields = ["id", "slug", "is_active"]

    def update(self, instance, validated_data):
        settings_data = self.context["request"].data.get("settings")
        instance = super().update(instance, validated_data)
        if isinstance(settings_data, dict):
            agency_settings, _ = AgencySettings.objects.get_or_create(agency=instance)
            serializer = AgencySettingsSerializer(agency_settings, data=settings_data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            instance.settings = serializer.instance
        return instance


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "code", "address", "phone", "email", "is_active"]
        read_only_fields = ["id"]
