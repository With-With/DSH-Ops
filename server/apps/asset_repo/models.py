"""
asset_repo 模型：页面对象 + 元素（PageObject / Element）。

元素是 search-first 匹配的核心资产：通过 URL + name + role 三级匹配，
避免重复录制/重复生成定位器，降低 token 消耗。
"""
from django.db import models

from apps.core.models import BaseModel


class PageObject(BaseModel):
    """页面对象：一个 URL 模式对应一个页面，承载一组元素。"""

    name = models.CharField("页面名称", max_length=128, db_index=True)
    url_pattern = models.CharField(
        "URL 模式",
        max_length=512,
        help_text="支持 {param} 占位，如 /users/{user_id}/profile",
    )
    notes = models.TextField("备注", blank=True, default="")

    class Meta:
        db_table = "asset_repo_pages"
        verbose_name = "页面对象"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["name"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.url_pattern})"


class Element(BaseModel):
    """页面元素：带候选定位器数组，支持 search-first 匹配。"""

    SOURCE_CHOICES = [
        ("recording", "录制生成"),
        ("manual", "手工维护"),
        ("api", "API 写入"),
    ]

    page = models.ForeignKey(
        PageObject,
        verbose_name="所属页面",
        on_delete=models.CASCADE,
        related_name="elements",
    )
    name = models.CharField("元素名称", max_length=128)
    role = models.CharField("ARIA 角色", max_length=64, blank=True, default="", db_index=True)
    candidates = models.JSONField(
        "定位器候选",
        default=list,
        blank=True,
        help_text="数组：[{type, value, priority, robustness}]，"
        "type ∈ role/text/label/placeholder/testid/css/xpath/aria_ref",
    )
    snapshot_hash = models.CharField(
        "快照哈希",
        max_length=128,
        blank=True,
        default="",
        db_index=True,
        help_text="元素视觉/结构快照的哈希，用于跨页复用匹配",
    )
    source = models.CharField(
        "来源",
        max_length=32,
        choices=SOURCE_CHOICES,
        default="manual",
        db_index=True,
    )
    notes = models.TextField("备注", blank=True, default="")

    class Meta:
        db_table = "asset_repo_elements"
        verbose_name = "页面元素"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["page", "name"]),
            models.Index(fields=["page", "role"]),
            models.Index(fields=["snapshot_hash"]),
        ]

    def __str__(self):
        return f"{self.name} [page={self.page_id}]"
