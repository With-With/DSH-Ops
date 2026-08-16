from django.db import models

from apps.core.models import BaseModel


class Recording(BaseModel):
    """录制脚本记录。

    存储 Playwright codegen 录制的原始脚本与解析后的结构化元数据。
    """

    LANGUAGE_CHOICES = [
        ("python", "Python"),
        ("javascript", "JavaScript"),
    ]

    FRAMEWORK_CHOICES = [
        ("playwright", "Playwright"),
        ("selenium", "Selenium"),
    ]

    name = models.CharField("录制名称", max_length=128)
    language = models.CharField(
        "语言",
        max_length=16,
        choices=LANGUAGE_CHOICES,
        default="python",
        db_index=True,
    )
    framework = models.CharField(
        "框架",
        max_length=16,
        choices=FRAMEWORK_CHOICES,
        default="playwright",
        db_index=True,
    )
    start_url = models.CharField("起始 URL", max_length=512, blank=True, default="")
    raw_content = models.TextField("原始脚本内容")
    normalized_content = models.TextField("归一化脚本内容", blank=True, default="")
    locators_count = models.IntegerField("定位器数量", default=0)
    actions_count = models.IntegerField("动作数量", default=0)
    warnings = models.JSONField("解析警告", default=list, blank=True)

    class Meta:
        verbose_name = "录制脚本"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.language}/{self.framework})"
