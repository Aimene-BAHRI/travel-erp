from rest_framework import serializers

from customers.models import Customer
from organizations.models import Branch


class CustomerSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    branch_name = serializers.CharField(source="branch.name", read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "kind",
            "first_name",
            "last_name",
            "company_name",
            "display_name",
            "phone",
            "email",
            "address",
            "notes",
            "branch",
            "branch_name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request and request.user.is_authenticated and request.user.agency_id:
            self.fields["branch"].queryset = Branch.objects.filter(agency=request.user.agency)
            self.fields["branch"].required = not bool(request.user.branch_id)

    def validate(self, attrs):
        kind = attrs.get("kind", self.instance.kind if self.instance else Customer.Kind.INDIVIDUAL)
        first_name = attrs.get("first_name", self.instance.first_name if self.instance else "")
        last_name = attrs.get("last_name", self.instance.last_name if self.instance else "")
        company_name = attrs.get(
            "company_name", self.instance.company_name if self.instance else ""
        )
        if kind == Customer.Kind.COMPANY and not company_name.strip():
            raise serializers.ValidationError({"company_name": "Company name is required."})
        if kind == Customer.Kind.INDIVIDUAL and not (first_name.strip() or last_name.strip()):
            raise serializers.ValidationError(
                "An individual customer requires a first or last name."
            )
        user = self.context["request"].user
        branch = attrs.get("branch", self.instance.branch if self.instance else user.branch)
        if user.branch_id and branch != user.branch:
            raise serializers.ValidationError({"branch": "Branch users must use their own branch."})
        if not branch:
            raise serializers.ValidationError({"branch": "A managing branch is required."})
        attrs["branch"] = branch
        return attrs
