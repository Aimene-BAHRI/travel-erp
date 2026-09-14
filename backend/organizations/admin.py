from django.contrib import admin

from .models import Agency, AgencySettings, Branch

admin.site.register(Agency)
admin.site.register(AgencySettings)
admin.site.register(Branch)
