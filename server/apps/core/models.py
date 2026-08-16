from django.db import models
from django.utils import timezone

from .managers import SoftDeleteManager


class BaseModel(models.Model):
    """所有业务模型的抽象基类。

    提供：
    - 创建/更新时间戳
    - 创建/更新人（可空，方便后台任务）
    - 软删除字段
    - 软删除管理器
    """

    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True, db_index=True)
    created_by = models.ForeignKey(
        "auth.User",
        verbose_name="创建人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_by = models.ForeignKey(
        "auth.User",
        verbose_name="更新人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    is_deleted = models.BooleanField("是否已删除", default=False, db_index=True)
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)

    objects = SoftDeleteManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self, using=None, keep_parents=False, hard=False):
        """软删除：设置 is_deleted=True + deleted_at；hard=True 时物理删除。"""
        if hard:
            return super().delete(using=using, keep_parents=keep_parents)
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

    def restore(self):
        """恢复软删除的记录。"""
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=["is_deleted", "deleted_at", "updated_at"])


class AuditLog(models.Model):
    """审计日志：记录关键操作（创建/删除/状态变更等）。

    不继承 BaseModel，因为审计日志本身不应被软删除——它是事实记录。
    只有 created_at / created_by，没有 updated 字段（不可修改）。
    """

    action = models.CharField("操作类型", max_length=64, db_index=True)
    target = models.CharField("操作对象", max_length=255, db_index=True)
    detail = models.JSONField("详细信息", default=dict, blank=True)
    created_by = models.ForeignKey(
        "auth.User",
        verbose_name="操作人",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "审计日志"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} - {self.target} ({self.created_at})"

