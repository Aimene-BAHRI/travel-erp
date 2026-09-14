from django.http import FileResponse
from drf_spectacular.utils import extend_schema
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.response import Response

from audit.services import record_event
from documents.models import Document

from .serializers import DocumentSerializer, DocumentUploadSerializer


class DocumentViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Document.objects.select_related(
        "branch", "traveler_link__traveler", "passport_link__passport", "trip_link__trip"
    )
    serializer_class = DocumentSerializer
    permission_classes = [DjangoModelPermissions]
    parser_classes = [MultiPartParser, FormParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "original_filename", "sha256"]
    ordering_fields = ["created_at", "title", "size_bytes"]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset().filter(agency=user.agency)
        if user.branch_id and not user.has_perm("documents.view_all_documents"):
            queryset = queryset.filter(branch=user.branch)
        owner_type = self.request.query_params.get("owner_type")
        owner_id = self.request.query_params.get("owner_id")
        if owner_type == "TRAVELER" and owner_id:
            queryset = queryset.filter(traveler_link__traveler_id=owner_id)
        elif owner_type == "PASSPORT" and owner_id:
            queryset = queryset.filter(passport_link__passport_id=owner_id)
        elif owner_type == "TRIP" and owner_id:
            queryset = queryset.filter(trip_link__trip_id=owner_id)
        return queryset

    @extend_schema(request=DocumentUploadSerializer, responses={201: DocumentSerializer})
    def create(self, request):
        serializer = DocumentUploadSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        record_event(
            actor=request.user,
            action="document.uploaded",
            target_type="documents.Document",
            target_id=document.pk,
            metadata={"category": document.category, "sha256": document.sha256},
            request=request,
        )
        return Response(
            DocumentSerializer(document, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def destroy(self, request, pk=None):
        document = self.get_object()
        document_id = document.pk
        stored_file = document.file
        record_event(
            actor=request.user,
            action="document.deleted",
            target_type="documents.Document",
            target_id=document_id,
            metadata={
                "category": document.category,
                "title": document.title,
                "sha256": document.sha256,
            },
            request=request,
        )
        document.delete()
        stored_file.delete(save=False)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        document = self.get_object()
        record_event(
            actor=request.user,
            action="document.downloaded",
            target_type="documents.Document",
            target_id=document.pk,
            request=request,
        )
        return FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=document.original_filename,
            content_type=document.mime_type,
        )
