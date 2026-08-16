"""
ai_config 模型：LLM 大模型提供方配置。

api_key_encrypted = Fernet 密文；api_key_mask = 回显掩码。
明文永不落库、永不回传。
"""
from django.db import models

from apps.core.models import BaseModel


class AIProviderConfig(BaseModel):
    """AI 大模型提供方配置（A1-A4 阶段与 gateway 直连预留）。"""

    PROVIDER_CHOICES = [
        ("deepseek", "DeepSeek"),
        ("volcark", "火山方舟 Ark"),
        ("openai_compatible", "OpenAI 兼容接口"),
        ("ollama", "Ollama"),
        ("custom", "自定义"),
    ]

    name = models.CharField("配置名称", max_length=64, unique=True)
    provider = models.CharField("提供方", max_length=32, choices=PROVIDER_CHOICES, db_index=True)
    base_url = models.CharField("Base URL", max_length=256, blank=True, default="")
    model_name = models.CharField("模型名", max_length=128)
    api_key_encrypted = models.TextField("API Key 密文", blank=True, default="")
    api_key_mask = models.CharField("API Key 掩码", max_length=64, blank=True, default="")
    enabled = models.BooleanField("启用", default=True, db_index=True)
    is_default = models.BooleanField("默认配置", default=False, db_index=True)
    extra = models.JSONField("扩展参数", default=dict, blank=True, help_text="temperature/max_tokens 等")
    remark = models.TextField("备注", blank=True, default="")

    class Meta:
        db_table = "ai_provider_configs"
        verbose_name = "AI 模型配置"
        verbose_name_plural = verbose_name
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"[{self.provider}] {self.name} ({self.model_name})"
