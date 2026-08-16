from django.db import models

from apps.core.models import BaseModel


class ReplayRun(BaseModel):
    """回放执行记录。

    记录一次回放任务的执行状态、耗时、步骤统计与 trace 产物路径。
    不建跨 app FK，用 recording_id (IntegerField 风格的 FK) 手动关联。
    """

    STATUS_CHOICES = [
        ("running", "运行中"),
        ("success", "成功"),
        ("failed", "失败"),
    ]

    recording = models.ForeignKey(
        "recorder.Recording",
        verbose_name="关联录制",
        on_delete=models.CASCADE,
        related_name="replay_runs",
    )
    task_set_id = models.IntegerField("关联任务集 ID", null=True, blank=True)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=STATUS_CHOICES,
        default="running",
        db_index=True,
    )
    duration_ms = models.IntegerField("耗时（毫秒）", default=0)
    steps_total = models.IntegerField("总步骤数", default=0)
    steps_passed = models.IntegerField("通过步骤数", default=0)
    error = models.TextField("错误信息", blank=True, default="")
    trace_path = models.CharField("Trace 文件路径", max_length=512, blank=True, default="")
    trace_hash = models.CharField("Trace 文件哈希", max_length=128, blank=True, default="")

    class Meta:
        verbose_name = "回放执行"
        verbose_name_plural = verbose_name
        ordering = ["-created_at"]

    def __str__(self):
        return f"ReplayRun #{self.pk} ({self.status})"
