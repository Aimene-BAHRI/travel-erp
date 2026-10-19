from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from organizations.models import Branch
from reference.models import Country
from travelers.models import Passport, Traveler
from travelers.services import save_passport


class PassportSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    nationality_code = serializers.CharField(source="nationality.code", read_only=True)
    passport_image_url = serializers.SerializerMethodField()

    def get_passport_image_url(self, obj) -> str | None:
        if not obj.passport_image_id:
            return None
        path = f"/api/v1/documents/{obj.passport_image_id}/download/"
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path

    class Meta:
        model = Passport
        fields = [
            "id",
            "passport_number",
            "full_name",
            "status",
            "birth_date",
            "gender",
            "expiry_date",
            "nationality_code",
            "passport_image_url",
        ]

    def get_full_name(self, obj) -> str:
        return " ".join(part for part in [obj.first_name, obj.middle_name, obj.last_name] if part)


class TravelerSerializer(serializers.ModelSerializer):
    branch_name = serializers.CharField(source="branch.name", read_only=True)
    current_passport = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()
    current_photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Traveler
        fields = [
            "id",
            "display_name",
            "first_name",
            "last_name",
            "birth_date",
            "gender",
            "phone",
            "email",
            "address",
            "notes",
            "branch",
            "branch_name",
            "current_photo",
            "current_photo_url",
            "current_photo_source",
            "current_passport",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "current_photo",
            "current_photo_url",
            "current_photo_source",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["branch"].queryset = Branch.objects.filter(agency=request.user.agency)
            self.fields["branch"].required = not bool(request.user.branch_id)

    def validate(self, attrs):
        if self.instance is None and "branch" not in attrs:
            user = self.context["request"].user
            if user.branch_id:
                attrs["branch"] = user.branch
            else:
                raise serializers.ValidationError({"branch": "A managing branch is required."})
        return attrs

    def validate_branch(self, branch):
        user = self.context["request"].user
        if user.branch_id and branch != user.branch:
            raise serializers.ValidationError("Branch users must use their own branch.")
        return branch

    @extend_schema_field(PassportSummarySerializer)
    def get_current_passport(self, obj):
        passport = next(
            (item for item in obj.passports.all() if item.status == Passport.Status.CURRENT), None
        )
        return PassportSummarySerializer(passport, context=self.context).data if passport else None

    def get_display_name(self, obj) -> str:
        passport = next(
            (item for item in obj.passports.all() if item.status == Passport.Status.CURRENT), None
        )
        if not passport:
            name = " ".join(part for part in [obj.first_name, obj.last_name] if part)
            return name or f"Traveler {str(obj.pk)[:8]}"
        return " ".join(part for part in [passport.first_name, passport.last_name] if part)

    def get_current_photo_url(self, obj) -> str | None:
        if not obj.current_photo_id:
            return None
        request = self.context.get("request")
        path = f"/api/v1/documents/{obj.current_photo_id}/download/"
        return request.build_absolute_uri(path) if request else path


class DocumentLinkSerializer(serializers.Serializer):
    document = serializers.UUIDField()
    source = serializers.ChoiceField(
        choices=Traveler.PhotoSource.choices, required=False, allow_blank=True
    )


class PassportMrzSerializer(serializers.Serializer):
    mrz = serializers.CharField(allow_blank=False)
    reference_date = serializers.DateField(required=False)


class PassportSerializer(serializers.ModelSerializer):
    birth_country = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all(), allow_null=True, required=False
    )
    nationality = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all())
    issuing_country = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all())

    class Meta:
        model = Passport
        fields = [
            "id",
            "traveler",
            "status",
            "passport_number",
            "first_name",
            "middle_name",
            "last_name",
            "birth_date",
            "birth_place",
            "birth_country",
            "nationality",
            "gender",
            "issue_date",
            "expiry_date",
            "issuing_country",
            "issue_place",
            "mrz",
            "passport_image",
            "ocr_raw_data",
            "ocr_source",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "passport_image",
            "ocr_raw_data",
            "ocr_source",
            "created_at",
            "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["traveler"].queryset = Traveler.objects.filter(agency=request.user.agency)

    def validate(self, attrs):
        issue_date = attrs.get("issue_date", self.instance.issue_date if self.instance else None)
        expiry_date = attrs.get("expiry_date", self.instance.expiry_date if self.instance else None)
        if issue_date and expiry_date and expiry_date < issue_date:
            raise serializers.ValidationError({"expiry_date": "Expiry cannot precede issue date."})
        return attrs

    def create(self, validated_data):
        return save_passport(actor=self.context["request"].user, **validated_data)

    def update(self, instance, validated_data):
        traveler = validated_data.pop("traveler", instance.traveler)
        return save_passport(
            instance=instance,
            traveler=traveler,
            actor=self.context["request"].user,
            **validated_data,
        )
