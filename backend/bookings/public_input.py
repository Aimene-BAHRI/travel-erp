import warnings

from PIL import Image, UnidentifiedImageError
from rest_framework import serializers
from rest_framework.throttling import AnonRateThrottle


class RequestThrottle(AnonRateThrottle):
    rate = "10/hour"


class PublicRequestInput(serializers.Serializer):
    trip = serializers.UUIDField()
    package = serializers.UUIDField(required=False, allow_null=True)
    customer_name = serializers.CharField(max_length=180)
    phone = serializers.CharField(max_length=40)
    email = serializers.EmailField(required=False, allow_blank=True)
    adults = serializers.IntegerField(min_value=1, max_value=99, default=1)
    children_with_bed = serializers.IntegerField(min_value=0, max_value=99, default=0)
    children_without_bed = serializers.IntegerField(min_value=0, max_value=99, default=0)
    infants = serializers.IntegerField(min_value=0, max_value=99, default=0)
    consent = serializers.BooleanField()
    passport_consent = serializers.BooleanField(default=False)
    expected_total = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=0, required=False
    )
    notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    preferred_room_type = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_consent(self, value):
        if not value:
            raise serializers.ValidationError("Consent is required.")
        return value


def validate_passport(upload):
    if not 0 < upload.size <= 10 * 1024 * 1024:
        raise serializers.ValidationError("Each passport image must be between 1 byte and 10 MB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload) as picture:
                if picture.format not in {"JPEG", "PNG", "WEBP"}:
                    raise serializers.ValidationError("Use a JPEG, PNG, or WebP passport image.")
                if picture.width * picture.height > 25_000_000:
                    raise serializers.ValidationError(
                        "Passport images must be under 25 megapixels."
                    )
                mime = Image.MIME[picture.format]
                picture.verify()
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise serializers.ValidationError("The passport image is invalid.") from exc
    finally:
        upload.seek(0)
    upload.content_type = mime
