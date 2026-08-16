"""
testdata 模型：P1 最小实现 —— ParameterSet。

与 contracts/matrix.schema.json 对齐的 secret 占位约定：
    values 中命中 secret_keys 的键，序列化输出时替换为 "${secret:<key>}"。
    POST 入参允许明文入库（P3 再加密存储）。
"""
from django.db import models

from apps.core.models import BaseModel


class ParameterSet(BaseModel):
    """参数集：一组键值对，可标记哪些键是 secret。"""

    name = models.CharField("参数集名称", max_length=128, unique=True)
    values = models.JSONField(
        "参数值",
        default=dict,
        blank=True,
        help_text="键值对字典。secret 键的明文在 P1 阶段直接入库，P3 加密。",
    )
    secret_keys = models.JSONField(
        "Secret 键列表",
        default=list,
        blank=True,
        help_text="values 中哪些 key 是 secret，序列化时会脱敏为 ${secret:<key>}",
    )

    class Meta:
        db_table = "testdata_parameter_sets"
        verbose_name = "参数集"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"ParameterSet: {self.name}"
