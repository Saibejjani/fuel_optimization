from django.contrib import admin

from api.models import FuelStops


@admin.register(FuelStops)
class FuelStopsAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "state", "price", "latitude", "longitude")
    list_filter = ("state",)
    search_fields = ("name", "city", "address")
    ordering = ("price",)
