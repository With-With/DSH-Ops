from django.db import models

from apps.core.models import BaseModel


class RuntimeInstance(BaseModel):
    """DSH 运行时实例。

    一个 RuntimeInstance 对应一套完整的 DSH 运行环境：
    - dsh 二进制路径
    - DSH_HOME 目录（含 profiles、memories 等）
    - Node.js 版本信息
    - 健康状态
    """

    STATUS_CHOICES = [
        ("unknown", "未知"),
        ("healthy", "健康"),
        ("warning", "警告"),
        ("error", "异常"),
    ]

    name = models.CharField("实例名称", max_length=128, unique=True)
    runtime_dir = models.CharField("运行时目录", max_length=512, blank=True, default="")
    dsh_bin_path = models.CharField("dsh 二进制路径", max_length=512, blank=True, default="")
    home_dir = models.CharField("DSH_HOME 目录", max_length=512, blank=True, default="")
    version = models.CharField("DSH 版本", max_length=64, blank=True, default="")
    node_version = models.CharField("Node.js 版本", max_length=64, blank=True, default="")
    status = models.CharField(
        "状态",
        max_length=16,
        choices=STATUS_CHOICES,
        default="unknown",
        db_index=True,
    )
    last_check_at = models.DateTimeField("最后检查时间", null=True, blank=True)
    notes = models.TextField("备注", blank=True, default="")
    is_default = models.BooleanField("是否默认", default=False, db_index=True)

    class Meta:
        verbose_name = "运行时实例"
        verbose_name_plural = verbose_name
        ordering = ["-is_default", "-created_at"]

    def __str__(self):
        return f"{self.name} ({self.version or 'unknown'})"
