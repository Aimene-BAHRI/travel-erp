from django.contrib import admin

from .models import (
    Booking,
    BookingAccommodation,
    BookingFlight,
    BookingSnapshot,
    BookingTraveler,
)

admin.site.register(Booking)
admin.site.register(BookingTraveler)
admin.site.register(BookingAccommodation)
admin.site.register(BookingFlight)
admin.site.register(BookingSnapshot)
