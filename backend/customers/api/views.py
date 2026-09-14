from rest_framework import filters, viewsets
from rest_framework.permissions import DjangoModelPermissions

from audit.services import record_event
from customers.models import Customer

from .serializers import CustomerSerializer


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.select_related("branch", "agency", "created_by")
    serializer_class = CustomerSerializer
    permission_classes = [DjangoModelPermissions]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["first_name", "last_name", "company_name", "phone", "email"]
    ordering_fields = ["first_name", "last_name", "company_name", "created_at"]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        queryset = super().get_queryset().filter(agency=user.agency)
        if user.branch_id and not user.has_perm("customers.view_all_customers"):
            queryset = queryset.filter(branch=user.branch)
        return queryset

    def perform_create(self, serializer):
        customer = serializer.save(agency=self.request.user.agency, created_by=self.request.user)
        self._audit("customer.created", customer, after=CustomerSerializer(customer).data)

    def perform_update(self, serializer):
        before = CustomerSerializer(self.get_object()).data
        customer = serializer.save()
        self._audit(
            "customer.updated", customer, before=before, after=CustomerSerializer(customer).data
        )

    def _audit(self, action, customer, before=None, after=None):
        record_event(
            actor=self.request.user,
            action=action,
            target_type="customers.Customer",
            target_id=customer.pk,
            before=before,
            after=after,
            request=self.request,
        )
