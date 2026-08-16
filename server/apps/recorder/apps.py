from django.apps import AppConfig


class RecorderConfig(AppConfig):
    """P1 - 测试录制模块：录制用户操作生成测试脚本。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.recorder"
    verbose_name = "录制"
