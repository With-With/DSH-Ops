"""testcases 模型：AI 重组产出的 POM 化 pytest 用例脚本。"""
from django.db import models

from apps.core.models import BaseModel


class TestCase(BaseModel):
    """UI 自动化用例：POM 脚手架生成的 pytest 脚本（完全独立、可直接运行）。"""

    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("ready", "就绪"),
        ("archived", "归档"),
    ]

    name = models.CharField("用例名称", max_length=128)
    recording_id = models.IntegerField("来源录制 ID", null=True, blank=True, db_index=True)
    content = models.TextField("POM pytest 脚本全文", blank=True, default="")
    source = models.CharField(
        "来源", max_length=32, default="ai_normalized",
        choices=[("ai_normalized", "AI 重组"), ("manual", "手动创建")],
        db_index=True,
    )
    status = models.CharField(
        "状态", max_length=16, choices=STATUS_CHOICES, default="ready", db_index=True
    )
    tags = models.JSONField("标签", default=list, blank=True)

    class Meta:
        db_table = "ui_test_cases"
        verbose_name = "UI 用例"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recording_id", "source"]),
        ]

    def __str__(self):
        return f"TestCase #{self.id} {self.name} [{self.status}]"
