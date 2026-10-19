import base64
import binascii
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import serializers
from documents.services import upload_document, validate_upload
from audit.services import record_event


def save_passport_image(passport, payload, request):
    """Keep the original scan separate from the cropped traveler portrait."""
    if not payload:
        return
    from django.conf import settings

    encoded = serializers.CharField(
        max_length=((settings.MAX_DOCUMENT_SIZE_BYTES + 2) // 3) * 4
    ).run_validation(payload.get("data"))
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise serializers.ValidationError({"passport_scan": "Invalid passport image."}) from exc
    image = serializers.ImageField().run_validation(
        SimpleUploadedFile("passport-image.jpg", decoded)
    )
    validate_upload(image)
    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(image.content_type)
    if not extension:
        raise serializers.ValidationError({"passport_scan": "Use a JPEG, PNG or WebP image."})
    image.name = f"passport-full-image.{extension}"
    document = upload_document(
        actor=request.user, uploaded_file=image, category="PASSPORT",
        title="Full passport image", owner_type="PASSPORT", owner_id=passport.pk,
        purpose="FULL_PASSPORT_IMAGE",
    )
    passport.passport_image = document
    passport.save(update_fields=["passport_image", "updated_at"])
    record_event(actor=request.user, action="passport.image_updated",
                 target_type="travelers.Passport", target_id=passport.pk)


def save_cropped_photo(person, payload, request):
    if not payload:
        return
    source = serializers.ChoiceField(choices=['PASSPORT_AUTO_CROP', 'PASSPORT_MANUAL_CROP']).run_validation(payload.get('source'))
    encoded = serializers.CharField(max_length=7_000_000).run_validation(payload.get('data'))
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise serializers.ValidationError('Invalid cropped photo.') from exc
    photo = serializers.ImageField().run_validation(SimpleUploadedFile('traveler-passport-photo.jpg', decoded, content_type='image/jpeg'))
    validate_upload(photo)
    document = upload_document(actor=request.user, uploaded_file=photo, category='PHOTO', title='Traveler passport photo', owner_type='TRAVELER', owner_id=person.pk, purpose=source)
    person.current_photo = document
    person.current_photo_source = source
    person.save(update_fields=['current_photo', 'current_photo_source', 'updated_at'])
    record_event(actor=request.user, action='traveler.photo_updated', target_type='travelers.Traveler', target_id=person.pk)
