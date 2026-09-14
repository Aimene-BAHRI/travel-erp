from django.contrib import admin

from .models import Promotion, Quote, QuoteLine, QuoteSnapshot, SeasonalFlightPrice, TripHotelPrice

admin.site.register(Promotion)
admin.site.register(TripHotelPrice)
admin.site.register(SeasonalFlightPrice)
admin.site.register(Quote)
admin.site.register(QuoteLine)
admin.site.register(QuoteSnapshot)

