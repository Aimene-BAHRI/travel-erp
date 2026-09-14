from django.contrib import admin

from .models import (
    CommissionPayment,
    Partner,
    PartnerAllocation,
    PartnerAllocationUsage,
    PartnerCommission,
)

admin.site.register(
    [Partner, PartnerAllocation, PartnerAllocationUsage, PartnerCommission, CommissionPayment]
)
