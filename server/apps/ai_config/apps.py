from django.apps import AppConfig


class AiConfigConfig(AppConfig):
    """P3 - AI 配置：AI 模型、密钥、参数的集中管理。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ai_config"
    verbose_name = "AI 配置"
