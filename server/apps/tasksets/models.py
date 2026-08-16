"""
tasksets 模型：TaskSet（任务集）+ StageJob（阶段作业）。

TaskSet 是录制→回放→抽取→设计→生成 的完整流水线的状态机载体，
correlation_uuid 作为跨系统 ID 关联链的起点。
"""
import uuid

from django.db import models

from apps.core.models import BaseModel


class TaskSet(BaseModel):
    """任务集：一个录制对应的完整流水线实例。"""

    STATUS_CHOICES = [
        ("created", "已创建"),
        ("replaying", "回放中"),
        ("replay_done", "回放完成"),
        ("extracting", "抽取中"),
        ("extract_done", "抽取完成"),
        ("designing", "设计中"),
        ("design_done", "设计完成"),
        ("reviewing", "评审中"),
        ("review_done", "评审通过"),
        ("generating", "生成中"),
        ("generate_done", "生成完成"),
        ("failed", "失败"),
    ]

    name = models.CharField("任务集名称", max_length=128)
    recording_id = models.IntegerField("录制 ID", db_index=True)
    correlation_uuid = models.UUIDField(
        "关联链 UUID",
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
        help_text="跨系统 ID 关联链的起点（recorder → replay → asset → testdata …）",
    )
    status = models.CharField(
        "状态",
        max_length=32,
        choices=STATUS_CHOICES,
        default="created",
        db_index=True,
    )
    current_stage = models.CharField("当前阶段", max_length=64, blank=True, default="")
    error = models.TextField("错误信息", blank=True, default="")

    class Meta:
        db_table = "tasksets"
        verbose_name = "任务集"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"TaskSet #{self.id} {self.name} [{self.status}]"


class StageJob(BaseModel):
    """阶段作业：TaskSet 每个阶段的执行记录。"""

    STAGE_CHOICES = [
        ("replay", "回放"),
        ("extract", "抽取"),
        ("design", "设计"),
        ("review", "评审"),
        ("generate", "生成"),
    ]

    STATUS_CHOICES = [
        ("running", "运行中"),
        ("success", "成功"),
        ("failed", "失败"),
    ]

    task_set = models.ForeignKey(
        TaskSet,
        verbose_name="所属任务集",
        on_delete=models.CASCADE,
        related_name="stage_jobs",
    )
    stage = models.CharField("阶段", max_length=32, choices=STAGE_CHOICES, db_index=True)
    status = models.CharField(
        "状态", max_length=16, choices=STATUS_CHOICES, default="running", db_index=True
    )
    external_ref = models.CharField(
        "外部引用",
        max_length=256,
        blank=True,
        default="",
        help_text="如 'replay:12'，关联 replay 那边的 ReplayRun",
    )
    detail = models.JSONField(
        "详细信息",
        default=dict,
        blank=True,
        help_text="duration / steps / trace_hash 等执行数据",
    )
    started_at = models.DateTimeField("开始时间", null=True, blank=True)
    finished_at = models.DateTimeField("结束时间", null=True, blank=True)

    class Meta:
        db_table = "taskset_stage_jobs"
        verbose_name = "阶段作业"
        verbose_name_plural = verbose_name
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["task_set", "stage"]),
            models.Index(fields=["task_set", "status"]),
        ]

    def __str__(self):
        return f"StageJob {self.stage} [{self.status}] (task_set={self.task_set_id})"


class GeneratedRun(BaseModel):
    """A4/A5 生成产物：DSH 生成的测试脚本与运行报告。

    script_content 冗余保存脚本全文（工作区文件可清理后仍可查看/复用）。
    """

    STATUS_CHOICES = [
        ("pass", "通过"),
        ("fail", "失败"),
    ]

    task_set_id = models.IntegerField("任务集 ID", db_index=True)
    stage_job = models.ForeignKey(
        StageJob,
        verbose_name="所属阶段作业",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="generated_runs",
    )
    invocation_id = models.IntegerField("关联调用 ID", null=True, blank=True, db_index=True)
    script_file = models.CharField("脚本文件名", max_length=256, blank=True, default="")
    script_content = models.TextField("脚本全文", blank=True, default="")
    report = models.JSONField("运行报告", default=dict, blank=True)
    status = models.CharField(
        "状态", max_length=16, choices=STATUS_CHOICES, default="fail", db_index=True
    )
    rounds = models.IntegerField("自修复轮数", default=0)
    duration_ms = models.IntegerField("耗时(ms)", default=0)

    class Meta:
        db_table = "taskset_generated_runs"
        verbose_name = "生成运行"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["task_set_id", "status"]),
        ]

    def __str__(self):
        return f"GeneratedRun #{self.id} {self.script_file} [{self.status}]"
