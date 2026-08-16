from django.apps import AppConfig


class TestdataConfig(AppConfig):
    """P1-P3 - 测试数据：测试数据的生成、管理与数据驱动测试。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.testdata"
    verbose_name = "测试数据"
