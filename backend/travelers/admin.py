from django.contrib import admin

from .models import Passport, PassportDocument, Traveler, TravelerDocument

admin.site.register(Traveler)
admin.site.register(Passport)
admin.site.register(TravelerDocument)
admin.site.register(PassportDocument)
