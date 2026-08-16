from django.apps import AppConfig


class ObsCenterConfig(AppConfig):
    """P1-P3 - 观测中心：日志、指标、追踪的统一观测平台。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.obs_center"
    verbose_name = "观测中心"
