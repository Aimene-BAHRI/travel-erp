from django.contrib import admin

from .models import (
    Trip,
    TripAllocationRoom,
    TripDocument,
    TripFlight,
    TripHotel,
    TripRoomAssignment,
    TripStop,
    TripTransport,
)

admin.site.register(Trip)
admin.site.register(TripStop)
admin.site.register(TripHotel)
admin.site.register(TripFlight)
admin.site.register(TripTransport)
admin.site.register(TripDocument)
admin.site.register(TripAllocationRoom)
admin.site.register(TripRoomAssignment)
