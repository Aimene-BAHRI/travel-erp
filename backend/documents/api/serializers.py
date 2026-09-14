from rest_framework import serializers

from documents.models import Document
from documents.services import upload_document, validate_upload


class DocumentSerializer(serializers.ModelSerializer):
    download_url = serializers.HyperlinkedIdentityField(
        view_name="document-download", lookup_field="pk"
    )
    owner_type = serializers.SerializerMethodField()
    owner_id = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "category",
            "title",
            "original_filename",
            "mime_type",
            "size_bytes",
            "sha256",
            "owner_type",
            "owner_id",
            "download_url",
            "created_at",
        ]

    def get_owner_type(self, obj) -> str | None:
        if hasattr(obj, "traveler_link"):
            return "TRAVELER"
        if hasattr(obj, "passport_link"):
            return "PASSPORT"
        if hasattr(obj, "trip_link"):
            return "TRIP"
        return None

    def get_owner_id(self, obj) -> str | None:
        if hasattr(obj, "traveler_link"):
            return str(obj.traveler_link.traveler_id)
        if hasattr(obj, "passport_link"):
            return str(obj.passport_link.passport_id)
        if hasattr(obj, "trip_link"):
            return str(obj.trip_link.trip_id)
        return None


class DocumentUploadSerializer(serializers.Serializer):
    file = serializers.FileField(write_only=True)
    category = serializers.ChoiceField(choices=Document.Category.choices)
    title = serializers.CharField(max_length=180)
    owner_type = serializers.ChoiceField(choices=["TRAVELER", "PASSPORT", "TRIP"])
    owner_id = serializers.UUIDField()
    purpose = serializers.CharField(max_length=80, required=False, allow_blank=True)

    def validate_file(self, uploaded_file):
        validate_upload(uploaded_file)
        return uploaded_file

    def create(self, validated_data):
        return upload_document(
            actor=self.context["request"].user,
            uploaded_file=validated_data.pop("file"),
            **validated_data,
        )
