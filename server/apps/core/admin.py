from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "target", "created_by", "created_at")
    list_filter = ("action", "created_at")
    search_fields = ("target", "detail")
    readonly_fields = ("created_at",)
