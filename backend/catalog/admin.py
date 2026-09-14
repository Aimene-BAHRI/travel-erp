from django.contrib import admin

from .models import Airline, Hotel, Room, RoomType, Supplier

admin.site.register(Supplier)
admin.site.register(Airline)
admin.site.register(Hotel)
admin.site.register(RoomType)
admin.site.register(Room)
