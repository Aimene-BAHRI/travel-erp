from django.contrib import admin

from .models import AgencyCurrency, City, Country, Currency, PassengerCategory, PaymentMethod

admin.site.register(Country)
admin.site.register(City)
admin.site.register(Currency)
admin.site.register(AgencyCurrency)
admin.site.register(PassengerCategory)
admin.site.register(PaymentMethod)
