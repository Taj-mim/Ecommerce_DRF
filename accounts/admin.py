from django.contrib import admin

from accounts.models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone_number", "city", "country", "updated_at")
    search_fields = ("user__username", "user__email", "phone_number", "city")
    list_filter = ("country", "city")
