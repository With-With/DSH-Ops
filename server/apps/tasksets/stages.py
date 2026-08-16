"""
tasksets A1/A2 智能体阶段编排。

核心职责：
    1. 构建 A1 / A2 阶段的指令（skill 文件 + schema 全文 + 上下文）
    2. 调用 AgentGateway 执行阶段
    3. 校验产物并入 ArtifactDraft
    4. A1 阶段做 search-first 并入元素仓（PageObject / Element）

所有跨 app 依赖均为 lazy import（函数内 import），
测试时通过 patch ``get_gateway`` 替换网关实现。
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from django.conf import settings
from django.db import connections
from django.utils import timezone

from .models import StageJob, TaskSet
from .services import _transition

if TYPE_CHECKING:
    pass


# 阶段级锁：每任务集一把，防止并发触发同一阶段（run_stage_async 使用）
_global_lock = threading.Lock()
_STAGE_LOCKS: dict[int, threading.Lock] = {}


def _stage_lock(task_set_id: int) -> threading.Lock:
    with _global_lock:
        return _STAGE_LOCKS.setdefault(task_set_id, threading.Lock())


# ---------------------------------------------------------------------------
# 网关获取函数（测试时 mock 这个）
# ---------------------------------------------------------------------------

def get_gateway():
    """获取 AgentGateway 实例。

    测试时用 ``unittest.mock.patch("apps.tasksets.stages.get_gateway")`` 替换。
    """
    from apps.agent_runtime.gateway import AgentGateway  # type: ignore

    return AgentGateway()


# ---------------------------------------------------------------------------
# 工具：读取 repo 中的 skill / schema 文件
# ---------------------------------------------------------------------------

def _repo_path(relative: str) -> Path:
    """将相对路径解析为 repo 根目录下的绝对路径。"""
    root = getattr(settings, "DSHOPS_REPO_ROOT", None) or Path(
        settings.BASE_DIR
    ).parent
    return Path(root) / relative


def _read_text_file(path: Path) -> str | None:
    """读文本文件，不存在返回 None。"""
    try:
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass
    return None


def _load_pom_schema() -> str:
    """读 pom.schema.json 全文（字符串），缺失则用最小 fallback。"""
    content = _read_text_file(_repo_path("contracts/pom.schema.json"))
    if content:
        return content
    # fallback：最小可用 schema 片段
    return json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "POM Schema (fallback)",
            "type": "object",
            "required": ["schema_version", "pages", "elements", "actions"],
            "properties": {
                "schema_version": {"type": "string"},
                "pages": {"type": "array"},
                "elements": {"type": "array"},
                "actions": {"type": "array"},
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def _load_matrix_schema() -> str:
    """读 matrix.schema.json 全文（字符串），缺失则用最小 fallback。"""
    content = _read_text_file(_repo_path("contracts/matrix.schema.json"))
    if content:
        return content
    return json.dumps(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Matrix Schema (fallback)",
            "type": "object",
            "required": ["schema_version", "pom_ref", "rows"],
            "properties": {
                "schema_version": {"type": "string"},
                "pom_ref": {"type": "string"},
                "rows": {"type": "array"},
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def _load_a1_skill() -> str:
    """读 pom-extraction SKILL.md，缺失则用最小 fallback 人设。"""
    content = _read_text_file(_repo_path("agent/skills/pom-extraction/SKILL.md"))
    if content:
        return content
    return (
        "# 角色：POM 提取器（A1）\n\n"
        "你是一位资深 UI 自动化工程师，擅长从录制脚本和 trace 快照中\n"
        "提取高质量的页面对象模型（POM）。输出必须严格符合给定的 JSON Schema。\n"
    )


def _load_tester_md() -> str:
    """读 tester.md（A2 人设），缺失则用最小 fallback。"""
    content = _read_text_file(_repo_path("agent/skills/tester.md"))
    if content:
        return content
    return (
        "# 角色：测试用例设计专家（A2）\n\n"
        "你是一位拥有10年经验的资深测试用例编写专家，能够根据 POM 精确生成\n"
        "高覆盖率的测试用例矩阵，包含正常路径与异常路径。\n"
    )


# ---------------------------------------------------------------------------
# 指令构建
# ---------------------------------------------------------------------------

def build_a1_instruction(recording) -> str:
    """构建 A1 抽取阶段的完整指令。

    组成：
        1. pom-extraction SKILL.md（角色说明）
        2. pom.schema.json 全文（输出契约）
        3. 录制动作序列 JSON
        4. 输出要求（只输出一个 ```json 围栏）
    """
    # 从录制中解析动作
    try:
        from apps.recorder.parser import parse_recording  # type: ignore

        result = parse_recording(recording.raw_content)
        actions = result["actions"]
    except Exception:
        actions = []

    skill = _load_a1_skill()
    schema = _load_pom_schema()
    actions_json = json.dumps(actions, ensure_ascii=False, indent=2)

    return (
        f"{skill}\n\n"
        f"## 输出契约（必须严格遵守）\n\n"
        "以下是 pom.schema.json 全文：\n"
        "```json\n"
        f"{schema}\n"
        "```\n\n"
        "## 录制动作序列\n\n"
        "以下是录制动作序列 JSON：\n"
        "```json\n"
        f"{actions_json}\n"
        "```\n\n"
        "请输出页面对象模型(POM)草案。"
        "只输出一个 ```json 围栏，内容符合上述 schema，不要任何其他文字。\n"
    )


def build_a2_instruction(recording, pom_content: dict) -> str:
    """构建 A2 设计阶段的完整指令。

    组成：
        1. tester.md 人设
        2. POM 草案 JSON
        3. 录制摘要（start_url / 动作数）
        4. matrix.schema.json 全文
        5. 输出要求
    """
    persona = _load_tester_md()
    schema = _load_matrix_schema()
    pom_json = json.dumps(pom_content, ensure_ascii=False, indent=2)

    start_url = getattr(recording, "start_url", "") or ""
    actions_count = getattr(recording, "actions_count", 0) or 0

    return (
        f"{persona}\n\n"
        f"## 任务\n\n"
        "基于以下 POM 草案，设计测试用例矩阵（scenario matrix）。\n\n"
        f"**录制摘要**：\n"
        f"- 起始 URL：{start_url}\n"
        f"- 动作总数：{actions_count}\n\n"
        "## POM 草案\n\n"
        "```json\n"
        f"{pom_json}\n"
        "```\n\n"
        "## 输出契约\n\n"
        "以下是 matrix.schema.json 全文，输出必须严格符合：\n"
        "```json\n"
        f"{schema}\n"
        "```\n\n"
        "只输出一个 ```json 围栏，符合 schema，输出测试用例矩阵草案，"
        "含正常路径与至少一条异常路径。\n"
    )


# ---------------------------------------------------------------------------
# search-first 并入元素仓
# ---------------------------------------------------------------------------

def _merge_pom_into_asset_repo(pom: dict) -> dict:
    """把 A1 产出的 POM 用 search-first 策略并入元素仓。

    规则：
        - 页面：按 url_pattern 精确匹配 PageObject，命中则复用，否则新建
        - 元素：对每个元素调用 matching.match_element(page_url, name, role, snapshot_hash)
          - high 置信度：复用，记入 reused
          - none：新建 Element（source="recording"），记入 created
          - medium：也新建（保守策略，中置信不足以免复用错误）

    返回 { "created": [element_ids...], "reused": [element_ids...] }
    """
    from apps.asset_repo.matching import match_element, match_page  # type: ignore
    from apps.asset_repo.models import Element, PageObject  # type: ignore

    created: list[int] = []
    reused: list[int] = []

    pages = pom.get("pages", []) or []
    elements = pom.get("elements", []) or []

    # page_id (pom 内) -> PageObject 实例
    page_map: dict[str, PageObject] = {}

    for page_data in pages:
        url_pattern = page_data.get("url_pattern", "")
        name = page_data.get("name") or f"page_{page_data.get('id', '')}"

        existing = match_page(url_pattern) if url_pattern else None
        if existing is not None:
            page_obj = existing
        else:
            page_obj = PageObject.objects.create(
                name=name,
                url_pattern=url_pattern,
            )
        page_map[page_data.get("id", "")] = page_obj

    for elem_data in elements:
        page_id = elem_data.get("page_id", "")
        page_obj = page_map.get(page_id)
        if page_obj is None:
            continue  # 页面对不上，跳过

        name = elem_data.get("name", "")
        role = elem_data.get("role", "")
        snapshot_hash = elem_data.get("snapshot_hash") or None
        candidates = elem_data.get("candidates", []) or []

        match_result = match_element(
            page_url=page_obj.url_pattern,
            name=name,
            role=role,
            snapshot_hash=snapshot_hash,
        )

        if match_result.get("confidence") == "high" and match_result.get("match"):
            reused.append(match_result["match"]["id"])
        else:
            new_el = Element.objects.create(
                page=page_obj,
                name=name,
                role=role,
                candidates=candidates,
                snapshot_hash=snapshot_hash or "",
                source="recording",
            )
            created.append(new_el.id)

    return {"created": created, "reused": reused}


# ---------------------------------------------------------------------------
# A1 抽取阶段主入口
# ---------------------------------------------------------------------------

def run_extract_stage(task_set: TaskSet, job: StageJob | None = None) -> TaskSet:
    """执行 A1 抽取阶段。

    幂等守卫：仅 replay_done 或 failed 状态可进入。
    成功 -> extract_done，失败 -> failed。

    job 参数：异步路径由调用方预先完成守卫/转换/建 StageJob 后传入，
    此处跳过 setup 只执行主体（见 run_stage_async）。
    """
    # ---- 守卫 + 建 StageJob（异步路径已由 run_stage_async 完成）-------------
    if job is None:
        if task_set.status not in ("replay_done", "failed"):
            raise ValueError(
                f"cannot run extract stage from status {task_set.status!r}"
            )

        # 失败重试路径：从 failed 进入也合法
        _transition(task_set, "extracting")
        task_set.current_stage = "extract"
        task_set.save(update_fields=["current_stage", "updated_at"])

        job = StageJob.objects.create(
            task_set=task_set,
            stage="extract",
            status="running",
            started_at=timezone.now(),
        )

    try:
        # ---- 取 recording ----------------------------------------------------
        try:
            from apps.recorder.models import Recording  # type: ignore

            recording = Recording.objects.get(pk=task_set.recording_id)
        except Exception as exc:
            raise RuntimeError(f"recording #{task_set.recording_id} not found: {exc}")

        # ---- 构建指令 + 调网关 ----------------------------------------------
        instruction = build_a1_instruction(recording)
        gateway = get_gateway()
        invocation = gateway.run_stage(
            "a1_extract",
            instruction,
            task_set_id=task_set.id,
            recording_id=task_set.recording_id,
        )

        # ---- 结果判断 -------------------------------------------------------
        if invocation.status != "success" or invocation.parsed_json is None:
            error_msg = (
                invocation.error
                or f"gateway status={invocation.status}, parsed_json=None"
            )
            job.status = "failed"
            job.finished_at = timezone.now()
            job.detail = {
                "error": error_msg,
                "invocation_id": getattr(invocation, "id", None),
                "duration_ms": getattr(invocation, "duration_ms", None),
            }
            job.save(
                update_fields=["status", "finished_at", "detail", "updated_at"]
            )
            _transition(task_set, "failed", error=error_msg)
            task_set.current_stage = ""
            task_set.save(update_fields=["current_stage", "updated_at"])
            return task_set

        parsed = invocation.parsed_json

        # ---- 校验 POM schema -----------------------------------------------
        try:
            from apps.agent_runtime.contracts import validate_pom  # type: ignore

            valid, errors = validate_pom(parsed)
        except Exception as exc:
            # 校验函数本身不可用时，视为校验失败（保守）
            valid = False
            errors = [f"validate_pom unavailable: {exc}"]

        # ---- 保存 ArtifactDraft（不论 valid 与否都保存，供排查）------------
        schema_version = (
            parsed.get("schema_version") if isinstance(parsed, dict) else None
        ) or "1.0.0-dev"
        try:
            from apps.agent_runtime.models import ArtifactDraft  # type: ignore

            draft = ArtifactDraft.objects.create(
                task_set_id=task_set.id,
                kind="pom",
                content=parsed,
                schema_version=schema_version,
                valid=bool(valid),
                validation_errors=errors if not valid else [],
                invocation_id=getattr(invocation, "id", None),
                status="draft",
            )
        except Exception:
            draft = None

        if not valid:
            job.status = "failed"
            job.finished_at = timezone.now()
            job.detail = {
                "error": "pom schema validation failed",
                "validation_errors": errors,
                "invocation_id": getattr(invocation, "id", None),
                "artifact_draft_id": getattr(draft, "id", None),
            }
            job.save(
                update_fields=["status", "finished_at", "detail", "updated_at"]
            )
            _transition(task_set, "failed", error="POM schema 校验失败")
            task_set.current_stage = ""
            task_set.save(update_fields=["current_stage", "updated_at"])
            return task_set

        # ---- search-first 并入元素仓 ---------------------------------------
        merge_detail = _merge_pom_into_asset_repo(parsed)

        # ---- 成功收尾 -------------------------------------------------------
        job.status = "success"
        job.finished_at = timezone.now()
        job.detail = {
            "duration_ms": getattr(invocation, "duration_ms", None),
            "invocation_id": getattr(invocation, "id", None),
            "artifact_draft_id": getattr(draft, "id", None),
            "elements": merge_detail,
        }
        job.external_ref = f"invocation:{getattr(invocation, 'id', '')}"
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "detail",
                "external_ref",
                "updated_at",
            ]
        )

        _transition(task_set, "extract_done")
        task_set.current_stage = ""
        task_set.save(update_fields=["current_stage", "updated_at"])

    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.finished_at = timezone.now()
        job.detail = {"error": str(exc), "stage": "extract"}
        job.save(update_fields=["status", "finished_at", "detail", "updated_at"])

        task_set.error = str(exc)
        _transition(task_set, "failed", error=str(exc))
        task_set.current_stage = ""
        task_set.save(update_fields=["current_stage", "updated_at"])

    return task_set


# ---------------------------------------------------------------------------
# A2 设计阶段主入口
# ---------------------------------------------------------------------------

def run_design_stage(task_set: TaskSet, job: StageJob | None = None) -> TaskSet:
    """执行 A2 设计阶段。

    守卫：仅 extract_done 可进入。
    成功 -> design_done，失败 -> failed。

    job 参数：异步路径由调用方预先完成守卫/转换/建 StageJob 后传入，
    此处跳过 setup 只执行主体（见 run_stage_async）。
    """
    # ---- 守卫 + 建 StageJob（异步路径已由 run_stage_async 完成）-------------
    if job is None:
        if task_set.status != "extract_done":
            raise ValueError(
                f"cannot run design stage from status {task_set.status!r}"
            )

        _transition(task_set, "designing")
        task_set.current_stage = "design"
        task_set.save(update_fields=["current_stage", "updated_at"])

        job = StageJob.objects.create(
            task_set=task_set,
            stage="design",
            status="running",
            started_at=timezone.now(),
        )

    try:
        # ---- 取最新有效 POM 草案 --------------------------------------------
        try:
            from apps.agent_runtime.models import ArtifactDraft  # type: ignore

            pom_draft = (
                ArtifactDraft.objects.filter(
                    task_set_id=task_set.id,
                    kind="pom",
                    valid=True,
                )
                .order_by("-created_at")
                .first()
            )
        except Exception as exc:
            raise RuntimeError(f"cannot load ArtifactDraft: {exc}")

        if pom_draft is None:
            raise RuntimeError("no valid POM draft found for design stage")

        # ---- 取 recording（用于摘要） ---------------------------------------
        try:
            from apps.recorder.models import Recording  # type: ignore

            recording = Recording.objects.get(pk=task_set.recording_id)
        except Exception:
            recording = None  # 录制拿不到也继续，摘要为空

        # ---- 构建指令 + 调网关 ----------------------------------------------
        instruction = build_a2_instruction(recording, pom_draft.content)
        gateway = get_gateway()
        invocation = gateway.run_stage(
            "a2_design",
            instruction,
            task_set_id=task_set.id,
            recording_id=task_set.recording_id,
        )

        # ---- 结果判断 -------------------------------------------------------
        if invocation.status != "success" or invocation.parsed_json is None:
            error_msg = (
                invocation.error
                or f"gateway status={invocation.status}, parsed_json=None"
            )
            job.status = "failed"
            job.finished_at = timezone.now()
            job.detail = {
                "error": error_msg,
                "invocation_id": getattr(invocation, "id", None),
                "duration_ms": getattr(invocation, "duration_ms", None),
            }
            job.save(
                update_fields=["status", "finished_at", "detail", "updated_at"]
            )
            _transition(task_set, "failed", error=error_msg)
            task_set.current_stage = ""
            task_set.save(update_fields=["current_stage", "updated_at"])
            return task_set

        parsed = invocation.parsed_json

        # ---- 校验 matrix schema --------------------------------------------
        try:
            from apps.agent_runtime.contracts import validate_matrix  # type: ignore

            valid, errors = validate_matrix(parsed)
        except Exception as exc:
            valid = False
            errors = [f"validate_matrix unavailable: {exc}"]

        schema_version = (
            parsed.get("schema_version") if isinstance(parsed, dict) else None
        ) or "1.0.0-dev"
        try:
            from apps.agent_runtime.models import ArtifactDraft  # type: ignore

            draft = ArtifactDraft.objects.create(
                task_set_id=task_set.id,
                kind="matrix",
                content=parsed,
                schema_version=schema_version,
                valid=bool(valid),
                validation_errors=errors if not valid else [],
                invocation_id=getattr(invocation, "id", None),
                status="draft",
            )
        except Exception:
            draft = None

        if not valid:
            job.status = "failed"
            job.finished_at = timezone.now()
            job.detail = {
                "error": "matrix schema validation failed",
                "validation_errors": errors,
                "invocation_id": getattr(invocation, "id", None),
                "artifact_draft_id": getattr(draft, "id", None),
            }
            job.save(
                update_fields=["status", "finished_at", "detail", "updated_at"]
            )
            _transition(task_set, "failed", error="Matrix schema 校验失败")
            task_set.current_stage = ""
            task_set.save(update_fields=["current_stage", "updated_at"])
            return task_set

        # ---- 成功收尾 -------------------------------------------------------
        job.status = "success"
        job.finished_at = timezone.now()
        job.detail = {
            "duration_ms": getattr(invocation, "duration_ms", None),
            "invocation_id": getattr(invocation, "id", None),
            "artifact_draft_id": getattr(draft, "id", None),
        }
        job.external_ref = f"invocation:{getattr(invocation, 'id', '')}"
        job.save(
            update_fields=[
                "status",
                "finished_at",
                "detail",
                "external_ref",
                "updated_at",
            ]
        )

        _transition(task_set, "design_done")
        task_set.current_stage = ""
        task_set.save(update_fields=["current_stage", "updated_at"])

    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.finished_at = timezone.now()
        job.detail = {"error": str(exc), "stage": "design"}
        job.save(update_fields=["status", "finished_at", "detail", "updated_at"])

        task_set.error = str(exc)
        _transition(task_set, "failed", error=str(exc))
        task_set.current_stage = ""
        task_set.save(update_fields=["current_stage", "updated_at"])

    return task_set


# ---------------------------------------------------------------------------
# 异步阶段入口（P2：POST /api/tasksets/<id>/stages/）
# ---------------------------------------------------------------------------

_STAGE_SPECS = {
    "extract": {
        "fn": run_extract_stage,
        "allowed": ("replay_done", "failed"),
        "running": "extracting",
        "current": "extract",
        "job_stage": "extract",
    },
    "design": {
        "fn": run_design_stage,
        "allowed": ("extract_done",),
        "running": "designing",
        "current": "design",
        "job_stage": "design",
    },
}


def run_stage_async(task_set: TaskSet, stage: str) -> TaskSet:
    """异步执行 A1/A2 阶段：状态转换 + StageJob 同步完成（202 语义即时生效），
    阶段主体在后台线程执行，完成后回写终态。

    守卫失败抛 ValueError（调用方转 409）；同任务集阶段已在执行则抛 ValueError。
    """
    spec = _STAGE_SPECS.get(stage)
    if spec is None:
        raise ValueError(f"unknown stage: {stage!r}")

    lock = _stage_lock(task_set.id)
    if not lock.acquire(blocking=False):
        raise ValueError(f"任务集 #{task_set.id} 已有阶段正在执行中")

    try:
        if task_set.status not in spec["allowed"]:
            raise ValueError(
                f"cannot run {stage} stage from status {task_set.status!r}"
            )

        # ---- 同步完成转换 + 建 StageJob --------------------------------------
        _transition(task_set, spec["running"])
        task_set.current_stage = spec["current"]
        task_set.save(update_fields=["current_stage", "updated_at"])

        job = StageJob.objects.create(
            task_set=task_set,
            stage=spec["job_stage"],
            status="running",
            started_at=timezone.now(),
        )
    except Exception:
        lock.release()
        raise

    ts_pk = task_set.pk
    job_pk = job.pk
    fn = spec["fn"]

    def _worker():
        try:
            from apps.tasksets.models import StageJob as _StageJob
            from apps.tasksets.models import TaskSet as _TaskSet

            ts = _TaskSet.objects.get(pk=ts_pk)
            j = _StageJob.objects.get(pk=job_pk)
            fn(ts, job=j)
        except Exception:  # fn 内部已兜底；此处仅防御未捕获路径
            try:
                from apps.tasksets.models import StageJob as _SJ

                j = _SJ.objects.get(pk=job_pk)
                j.status = "failed"
                j.detail = {**j.detail, "error": "uncaught in stage worker"}
                j.save(update_fields=["status", "detail", "updated_at"])
            except Exception:
                pass
        finally:
            lock.release()
            connections.close_all()

    threading.Thread(target=_worker, daemon=True, name=f"taskset-stage-{stage}-{ts_pk}").start()
    return task_set
