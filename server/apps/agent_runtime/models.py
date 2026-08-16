"""
agent_runtime 模型：Agent 调用记录与草案存储。

AgentInvocation：每次 DSH agent 调用的完整记录（指令、输出、状态、耗时等）。
ArtifactDraft：Agent 产出的 POM / Matrix 草案，待评审通过后入库资产仓。
"""
from django.db import models

from apps.core.models import BaseModel


class AgentInvocation(BaseModel):
    """DSH Agent 单次调用记录。"""

    STATUS_CHOICES = [
        ("success", "成功"),
        ("failed", "失败"),
        ("timeout", "超时"),
        ("error", "错误"),
    ]

    stage = models.CharField("阶段", max_length=64, db_index=True, help_text="如 pom_extract / matrix_design")
    task_set_id = models.IntegerField("任务集 ID", null=True, blank=True, db_index=True)
    recording_id = models.IntegerField("录制 ID", null=True, blank=True, db_index=True)
    instruction = models.TextField("指令文本")
    instruction_sha = models.CharField("指令 SHA256", max_length=64, db_index=True)
    output_text = models.TextField("输出文本", blank=True, default="")
    parsed_json = models.JSONField("解析 JSON", null=True, blank=True)
    status = models.CharField("状态", max_length=16, choices=STATUS_CHOICES, db_index=True)
    exit_code = models.IntegerField("退出码", null=True, blank=True)
    duration_ms = models.IntegerField("耗时(ms)", default=0)
    mock = models.BooleanField("是否 Mock", default=False, db_index=True)
    error = models.TextField("错误信息", blank=True, default="")

    class Meta:
        db_table = "agent_runtime_invocations"
        verbose_name = "Agent 调用记录"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["stage", "status"]),
            models.Index(fields=["task_set_id", "stage"]),
        ]

    def __str__(self):
        return f"[{self.status}] {self.stage} ({self.id})"


class ArtifactDraft(BaseModel):
    """Agent 产出的草案（POM / Matrix），待评审。"""

    KIND_CHOICES = [
        ("pom", "POM 页面对象模型"),
        ("matrix", "场景矩阵"),
    ]

    STATUS_CHOICES = [
        ("draft", "草稿"),
        ("approved", "已通过"),
        ("rejected", "已驳回"),
    ]

    task_set_id = models.IntegerField("任务集 ID", null=True, blank=True, db_index=True)
    kind = models.CharField("类型", max_length=16, choices=KIND_CHOICES, db_index=True)
    content = models.JSONField("内容")
    schema_version = models.CharField("契约版本", max_length=32, default="0.1.0")
    valid = models.BooleanField("是否通过契约校验", default=False, db_index=True)
    validation_errors = models.JSONField("校验错误列表", default=list, blank=True)
    status = models.CharField("评审状态", max_length=16, choices=STATUS_CHOICES, default="draft", db_index=True)
    review_note = models.TextField("评审备注", blank=True, default="")
    invocation_id = models.IntegerField("关联调用 ID", null=True, blank=True, db_index=True)
    reviewed_at = models.DateTimeField("评审时间", null=True, blank=True)

    class Meta:
        db_table = "agent_runtime_drafts"
        verbose_name = "产物草案"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["kind", "status"]),
            models.Index(fields=["task_set_id", "kind"]),
        ]

    def __str__(self):
        return f"[{self.status}] {self.kind} draft ({self.id})"
