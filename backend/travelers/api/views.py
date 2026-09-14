from django.db.models import Prefetch
from django.utils import timezone
from rest_framework import filters, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response

from audit.services import record_event
from documents.models import Document
from travelers.models import Passport, Traveler
from travelers.rules import parse_td3_mrz

from .serializers import (
    DocumentLinkSerializer,
    PassportMrzSerializer,
    PassportSerializer,
    TravelerSerializer,
)


class TravelerViewSet(viewsets.ModelViewSet):
    queryset = Traveler.objects.select_related("branch").prefetch_related(
        Prefetch("passports", queryset=Passport.objects.select_related("nationality"))
    )
    serializer_class = TravelerSerializer
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        "phone",
        "email",
        "passports__passport_number",
        "passports__first_name",
        "passports__last_name",
    ]
    ordering_fields = ["created_at", "updated_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset().filter(agency=user.agency).distinct()
        if user.branch_id and not user.has_perm("travelers.view_all_travelers"):
            queryset = queryset.filter(branch=user.branch)
        return queryset

    def perform_create(self, serializer):
        traveler = serializer.save(agency=self.request.user.agency, created_by=self.request.user)
        self._audit("traveler.created", traveler)

    def perform_update(self, serializer):
        traveler = serializer.save()
        self._audit("traveler.updated", traveler)

    @action(detail=True, methods=["post"], url_path="set-current-photo")
    def set_current_photo(self, request, pk=None):
        traveler = self.get_object()
        input_serializer = DocumentLinkSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        document = Document.objects.filter(
            pk=input_serializer.validated_data["document"],
            agency=request.user.agency,
            category=Document.Category.PHOTO,
            traveler_link__traveler=traveler,
        ).first()
        if document is None:
            raise serializers.ValidationError("Photo document must belong to this traveler.")
        traveler.current_photo = document
        traveler.current_photo_source = input_serializer.validated_data.get("source", "")
        traveler.full_clean()
        traveler.save(update_fields=["current_photo", "current_photo_source", "updated_at"])
        self._audit("traveler.photo_updated", traveler)
        return Response(self.get_serializer(traveler).data)

    def _audit(self, action, traveler):
        record_event(
            actor=self.request.user,
            action=action,
            target_type="travelers.Traveler",
            target_id=traveler.pk,
            request=self.request,
        )


class PassportViewSet(viewsets.ModelViewSet):
    queryset = Passport.objects.select_related(
        "traveler", "nationality", "birth_country", "issuing_country"
    )
    serializer_class = PassportSerializer
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["passport_number", "first_name", "middle_name", "last_name"]
    ordering_fields = ["issue_date", "expiry_date", "created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset().filter(agency=user.agency)
        if user.branch_id and not user.has_perm("travelers.view_all_travelers"):
            queryset = queryset.filter(traveler__branch=user.branch)
        traveler_id = self.request.query_params.get("traveler")
        return queryset.filter(traveler_id=traveler_id) if traveler_id else queryset

    def perform_create(self, serializer):
        passport = serializer.save()
        self._audit("passport.created", passport)

    def perform_update(self, serializer):
        passport = serializer.save()
        self._audit("passport.updated", passport)

    @action(detail=False, methods=["post"], url_path="parse-mrz")
    def parse_mrz(self, request):
        input_serializer = PassportMrzSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        try:
            result = parse_td3_mrz(
                input_serializer.validated_data["mrz"],
                reference_date=input_serializer.validated_data.get(
                    "reference_date", timezone.localdate()
                ),
            )
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return Response(result)

    @action(detail=True, methods=["post"], url_path="set-image")
    def set_image(self, request, pk=None):
        passport = self.get_object()
        input_serializer = DocumentLinkSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        document = Document.objects.filter(
            pk=input_serializer.validated_data["document"],
            agency=request.user.agency,
            category=Document.Category.PASSPORT,
            passport_link__passport=passport,
        ).first()
        if document is None:
            raise serializers.ValidationError("Passport image must belong to this passport.")
        passport.passport_image = document
        passport.save(update_fields=["passport_image", "updated_at"])
        self._audit("passport.image_updated", passport)
        return Response(self.get_serializer(passport).data)

    def _audit(self, action, passport):
        record_event(
            actor=self.request.user,
            action=action,
            target_type="travelers.Passport",
            target_id=passport.pk,
            metadata={"passport_number": passport.passport_number},
            request=self.request,
        )
