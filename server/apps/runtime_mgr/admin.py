from django.contrib import admin

from .models import RuntimeInstance


@admin.register(RuntimeInstance)
class RuntimeInstanceAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "version",
        "status",
        "is_default",
        "last_check_at",
        "created_at",
    )
    list_filter = ("status", "is_default", "is_deleted")
    search_fields = ("name", "version", "dsh_bin_path", "home_dir")
    readonly_fields = ("created_at", "updated_at", "last_check_at")
