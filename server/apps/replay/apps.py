from django.apps import AppConfig


class ReplayConfig(AppConfig):
    """P1 - 测试回放模块：执行录制脚本并比对结果。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.replay"
    verbose_name = "回放"
