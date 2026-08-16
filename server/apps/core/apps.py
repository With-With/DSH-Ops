from django.apps import AppConfig


class CoreConfig(AppConfig):
    """核心模块：提供 BaseModel、SoftDeleteManager、AuditLog 等公共基类。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "核心"
