"""apps 定义：testcases（用例管理）。"""
from django.apps import AppConfig


class TestcasesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.testcases"
    verbose_name = "用例管理"
