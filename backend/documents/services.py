import hashlib

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from travelers.models import Passport, PassportDocument, Traveler, TravelerDocument
from trips.models import Trip, TripDocument

from .models import Document


def _get_owner(*, agency, owner_type, owner_id):
    if owner_type == "TRAVELER":
        return Traveler.objects.filter(agency=agency).select_related("branch").get(pk=owner_id)
    if owner_type == "PASSPORT":
        return (
            Passport.objects.filter(agency=agency)
            .select_related("traveler__branch")
            .get(pk=owner_id)
        )
    if owner_type == "TRIP":
        return Trip.objects.filter(agency=agency).select_related("branch").get(pk=owner_id)
    raise ValidationError({"owner_type": "Unsupported document owner type."})


@transaction.atomic
def upload_document(*, actor, uploaded_file, category, title, owner_type, owner_id, purpose=""):
    try:
        owner = _get_owner(
            agency=actor.agency,
            owner_type=owner_type,
            owner_id=owner_id,
        )
    except (Traveler.DoesNotExist, Passport.DoesNotExist, Trip.DoesNotExist) as exc:
        raise PermissionDenied("The document owner is unavailable.") from exc

    branch = owner.branch if owner_type in {"TRAVELER", "TRIP"} else owner.traveler.branch
    if (
        actor.branch_id
        and actor.branch_id != branch.id
        and not actor.has_perm("documents.view_all_documents")
    ):
        raise PermissionDenied("The document owner is outside your branch scope.")

    digest = hashlib.sha256()
    for chunk in uploaded_file.chunks():
        digest.update(chunk)
    uploaded_file.seek(0)
    document = Document.objects.create(
        agency=actor.agency,
        branch=branch,
        category=category,
        title=title,
        file=uploaded_file,
        original_filename=uploaded_file.name,
        mime_type=uploaded_file.content_type or "application/octet-stream",
        size_bytes=uploaded_file.size,
        sha256=digest.hexdigest(),
        uploaded_by=actor,
    )
    if owner_type == "TRAVELER":
        TravelerDocument.objects.create(traveler=owner, document=document, purpose=purpose)
    elif owner_type == "PASSPORT":
        PassportDocument.objects.create(passport=owner, document=document, purpose=purpose)
    else:
        TripDocument.objects.create(trip=owner, document=document, purpose=purpose)
    return document


def validate_upload(uploaded_file):
    if uploaded_file.size > settings.MAX_DOCUMENT_SIZE_BYTES:
        raise ValidationError(f"Files cannot exceed {settings.MAX_DOCUMENT_SIZE_BYTES} bytes.")
    if uploaded_file.content_type not in settings.ALLOWED_DOCUMENT_MIME_TYPES:
        raise ValidationError("This file type is not allowed.")
