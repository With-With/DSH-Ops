"""
tasksets 状态机服务。

核心职责：
    1. 创建 TaskSet
    2. 驱动各阶段执行（replay / extract / design / generate …）
    3. 守卫合法的状态转换

注意：
    对 replay 的依赖是 **lazy import**（函数内 import），
    避免 migration / import-time 依赖 apps.replay 的模型。
    若 replay 未就绪，优雅降级而不是 500。
"""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from django.utils import timezone

from .models import StageJob, TaskSet

if TYPE_CHECKING:
    pass  # 避免循环导入


# ---------------------------------------------------------------------------
# 状态机转换表
# ---------------------------------------------------------------------------

# allowed_transitions[当前状态] = 允许转换到的状态集合
allowed_transitions: dict[str, set[str]] = {
    "created": {"replaying", "failed"},
    "replaying": {"replay_done", "failed"},
    "replay_done": {"extracting", "failed"},
    "extracting": {"extract_done", "failed"},
    "extract_done": {"designing", "failed"},
    "designing": {"design_done", "failed"},
    "design_done": {"failed"},
    "failed": {"extracting"},  # 失败后可重入抽取阶段（重试路径）
}


def can_transition(current: str, next_: str) -> bool:
    """判断 current → next_ 是否合法。

    Args:
        current: 当前状态
        next_: 目标状态

    Returns:
        True 表示合法

    Raises:
        ValueError: 非法转换时抛出，message 说明原因
    """
    if current not in allowed_transitions:
        raise ValueError(f"unknown current status: {current!r}")
    if next_ not in {s for sset in allowed_transitions.values() for s in sset} and next_ not in allowed_transitions:
        raise ValueError(f"unknown target status: {next_!r}")
    if next_ not in allowed_transitions[current]:
        raise ValueError(
            f"illegal transition: {current!r} -> {next_!r}; "
            f"allowed targets: {sorted(allowed_transitions[current])}"
        )
    return True


def _transition(task_set: TaskSet, next_status: str, error: str = "") -> TaskSet:
    """执行状态转换（带守卫）。"""
    can_transition(task_set.status, next_status)
    task_set.status = next_status
    if error:
        task_set.error = error
    task_set.save(update_fields=["status", "error", "updated_at"])
    return task_set


# ---------------------------------------------------------------------------
# 创建
# ---------------------------------------------------------------------------

def create_task_set(name: str, recording_id: int) -> TaskSet:
    """创建一个新的 TaskSet（状态 = created）。"""
    task_set = TaskSet.objects.create(
        name=name,
        recording_id=recording_id,
        status="created",
        current_stage="",
    )
    return task_set


# ---------------------------------------------------------------------------
# replay 阶段
# ---------------------------------------------------------------------------

def run_replay_stage(task_set: TaskSet, headless: bool | None = None) -> TaskSet:
    """执行 replay 阶段：

    1. created → replaying，建 StageJob(replay, running)
    2. lazy import apps.replay.runner.run_replay 并调用
    3. 成功：StageJob success，TaskSet → replay_done
    4. 失败 / 异常：StageJob failed，TaskSet → failed，error 记录
    5. 若 replay 模块根本不可用：优雅降级，StageJob 标 failed，detail 记原因

    Args:
        task_set: 要执行的 TaskSet
        headless: 是否无头模式（透传给 replay runner）

    Returns:
        更新后的 TaskSet
    """
    # ---- 守卫 + 建 StageJob -------------------------------------------------
    _transition(task_set, "replaying")
    task_set.current_stage = "replay"
    task_set.save(update_fields=["current_stage", "updated_at"])

    job = StageJob.objects.create(
        task_set=task_set,
        stage="replay",
        status="running",
        started_at=timezone.now(),
    )

    # ---- 调用 replay（lazy import + 异常兜底） ------------------------------
    try:
        # 函数内 import，避免 migration 时依赖 replay app
        from apps.replay.runner import run_replay  # type: ignore
    except (ImportError, ModuleNotFoundError, AttributeError) as exc:
        # replay 服务不可用（A 未完成 / 未装 playwright 等）
        job.status = "failed"
        job.finished_at = timezone.now()
        job.detail = {
            "error": "replay service unavailable",
            "detail": str(exc),
        }
        job.save(update_fields=["status", "finished_at", "detail", "updated_at"])

        task_set.error = f"replay service unavailable: {exc}"
        _transition(task_set, "failed", error=task_set.error)
        return task_set

    try:
        # A 的实现签名：run_replay(recording, task_set_id=None, headless=None)
        # 这里我们传 recording_id 对应的 recording 模型实例；
        # 因为跨 app 禁止 FK，用整数字段 + runtime lazy import。
        try:
            from apps.recorder.models import Recording  # type: ignore
            recording = Recording.objects.get(pk=task_set.recording_id)
        except Exception:
            # 如果连 recording 模型也拿不到，直接传 None 或 id ——
            # 由 replay 那边决定是否兼容。这里尽量保底：
            recording = task_set.recording_id  # type: ignore

        result = run_replay(recording, task_set_id=task_set.id, headless=headless)

        # ---- 成功收尾 --------------------------------------------------------
        job.status = "success"
        job.finished_at = timezone.now()
        job.detail = _extract_replay_detail(result, job.started_at)
        # 如果 replay 返回了 ReplayRun 的 id，记到 external_ref
        replay_id = getattr(result, "id", None) or (
            result.get("id") if isinstance(result, dict) else None
        )
        if replay_id:
            job.external_ref = f"replay:{replay_id}"
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "detail",
                "external_ref",
                "updated_at",
            ]
        )

        _transition(task_set, "replay_done")
        task_set.current_stage = ""
        task_set.save(update_fields=["current_stage", "updated_at"])

    except Exception as exc:  # noqa: BLE001
        # 回放运行时异常
        job.status = "failed"
        job.finished_at = timezone.now()
        job.detail = {
            "error": str(exc),
            "stage": "replay",
        }
        job.save(update_fields=["status", "finished_at", "detail", "updated_at"])

        task_set.error = str(exc)
        _transition(task_set, "failed", error=str(exc))

    return task_set


def _extract_replay_detail(result, started_at: datetime | None) -> dict:
    """从 replay 返回值中抽取统一的 detail 字段。"""
    detail: dict = {}
    if isinstance(result, dict):
        detail["duration"] = result.get("duration")
        detail["steps"] = result.get("steps")
        detail["trace_hash"] = result.get("trace_hash")
    else:
        # 模型实例或其他对象：尝试读属性
        for attr in ("duration", "steps", "trace_hash"):
            val = getattr(result, attr, None)
            if val is not None:
                detail[attr] = val

    # 如果没带 duration，自己算
    if not detail.get("duration") and started_at:
        delta = (timezone.now() - started_at).total_seconds()
        detail["duration"] = round(delta, 2)

    return detail
