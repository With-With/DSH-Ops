from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    """P2 - 评审模块：测试用例/结果的评审工作流。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reviews"
    verbose_name = "评审"
