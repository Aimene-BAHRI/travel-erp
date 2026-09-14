from rest_framework import status, viewsets
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import DjangoModelPermissions, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.services import record_event
from organizations.models import AgencySettings, Branch
from reference.models import AgencyCurrency, PassengerCategory, PaymentMethod

from .serializers import AgencySerializer, BranchSerializer


class CurrentAgencyView(RetrieveUpdateAPIView):
    serializer_class = AgencySerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user.agency

    def perform_update(self, serializer):
        before = AgencySerializer(self.get_object()).data
        agency = serializer.save()
        record_event(
            actor=self.request.user,
            action="agency.updated",
            target_type="organizations.Agency",
            target_id=agency.pk,
            before=before,
            after=AgencySerializer(agency).data,
            request=self.request,
        )


class AgencySetupView(APIView):
    permission_classes = [IsAuthenticated]

    def checklist(self, agency):
        identity_complete = all(
            [agency.name, agency.legal_name, agency.address, agency.phone, agency.email]
        )
        return [
            {
                "key": "identity",
                "label": "Agency identity and contact details",
                "complete": identity_complete,
                "section": "agency",
            },
            {
                "key": "branch",
                "label": "At least one active branch",
                "complete": agency.branches.filter(is_active=True).exists(),
                "section": "operations",
            },
            {
                "key": "admin",
                "label": "At least one active administrator",
                "complete": agency.users.filter(is_active=True, is_staff=True).exists(),
                "section": "agency",
            },
            {
                "key": "currency",
                "label": "Accounting currency selected",
                "complete": AgencyCurrency.objects.filter(
                    agency=agency, is_enabled=True, is_accounting=True
                ).exists(),
                "section": "operations",
            },
            {
                "key": "payment_method",
                "label": "At least one active payment method",
                "complete": PaymentMethod.objects.filter(agency=agency, is_active=True).exists()
                or PaymentMethod.objects.filter(agency__isnull=True, is_active=True).exists(),
                "section": "operations",
            },
            {
                "key": "traveler_category",
                "label": "Traveler categories available",
                "complete": PassengerCategory.objects.filter(agency=agency, is_active=True).exists()
                or PassengerCategory.objects.filter(agency__isnull=True, is_active=True).exists(),
                "section": "operations",
            },
        ]

    def get(self, request):
        agency = request.user.agency
        agency_settings, _ = AgencySettings.objects.get_or_create(agency=agency)
        items = self.checklist(agency)
        complete_count = sum(item["complete"] for item in items)
        if agency_settings.setup_status != AgencySettings.SetupStatus.ACTIVE:
            computed = (
                AgencySettings.SetupStatus.READY
                if complete_count == len(items)
                else AgencySettings.SetupStatus.SETUP
            )
            if agency_settings.setup_status != computed:
                agency_settings.setup_status = computed
                agency_settings.save(update_fields=["setup_status", "updated_at"])
        return Response(
            {
                "status": agency_settings.setup_status,
                "complete_count": complete_count,
                "total_count": len(items),
                "items": items,
            }
        )

    def post(self, request):
        agency = request.user.agency
        agency_settings, _ = AgencySettings.objects.get_or_create(agency=agency)
        items = self.checklist(agency)
        if not all(item["complete"] for item in items):
            return Response(
                {"detail": "Complete all required setup items before activation.", "items": items},
                status=status.HTTP_400_BAD_REQUEST,
            )
        agency_settings.setup_status = AgencySettings.SetupStatus.ACTIVE
        agency_settings.save(update_fields=["setup_status", "updated_at"])
        record_event(
            actor=request.user,
            action="agency.setup_activated",
            target_type="organizations.Agency",
            target_id=agency.pk,
            request=request,
        )
        return self.get(request)


class BranchViewSet(viewsets.ModelViewSet):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [DjangoModelPermissions]

    def get_queryset(self):
        user = self.request.user
        queryset = Branch.objects.filter(agency=user.agency)
        if user.branch_id and not user.has_perm("organizations.view_all_branches"):
            queryset = queryset.filter(pk=user.branch_id)
        return queryset

    def perform_create(self, serializer):
        branch = serializer.save(agency=self.request.user.agency)
        record_event(
            actor=self.request.user,
            action="branch.created",
            target_type="organizations.Branch",
            target_id=branch.pk,
            after=BranchSerializer(branch).data,
            request=self.request,
        )

    def perform_update(self, serializer):
        before = BranchSerializer(self.get_object()).data
        branch = serializer.save()
        record_event(
            actor=self.request.user,
            action="branch.updated",
            target_type="organizations.Branch",
            target_id=branch.pk,
            before=before,
            after=BranchSerializer(branch).data,
            request=self.request,
        )
