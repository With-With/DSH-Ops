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

from .models import GeneratedRun, StageJob, TaskSet
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
        "含正常路径与至少一条异常路径。\n\n"
        "## 质量要求（A3 评审自动门会逐条核验，不满足将被驳回）\n\n"
        "1. **flow 必须是动作索引数组（int[]）**，引用 pom.json actions 的 index；"
        "禁止自由文本描述（如“刷新当前页面“），POM 没有的动作不要写进 flow。\n"
        "2. **每个异常场景的参数必须独立命名**：如“错误密码”场景用新参数 "
        "wrong_password（在 params 中给出具体值），禁止复用/引用正确值的 secret（"
        "${secret:password} 表示正确密码，与错误场景意图矛盾）。\n"
        "3. **assertion_hints 必须可执行且与期望一致**：期望“登录成功”就断言成功文案；"
        "期望“失败提示”就断言失败文案；一数据行只对应一个分支，不要一个断言集合覆盖"
        "互相矛盾的两条分支。\n"
        "4. **url_changed 断言必须给出期望目标 URL**（相对路径即可）。\n"
        "5. **每行都至少有一条明确可执行的断言**；若期望“不发起请求”（客户端校验），"
        "断言要落在“错误提示可见且页面未跳转”，不要写网络层无法验证的断言。\n"
        "6. **避免账号锁定污染**：连续失败锁定类场景（如 6 次错误密码）要么设计数据隔离，"
        "要么 needs_mock=true 并说明 mock 方式；不要把锁定状态带入依赖同一账号的后继用例。\n"
        "7. **跳转后页面**：若动作进入新页面，确认该页面在 pom.json 的 pages 中定义，"
        "否则相关断言无法判定。\n"
        "8. **场景范围**：优先设计页面元素**实际能表达**的用例（正常路径、字段为空、"
        "错误凭据等，错误提示文案以页面实际文案为准）；网络层异常（断网/超时/500/响应缓慢）"
        "可设计但必须 needs_mock=true 并说明 mock 方式。除非 POM 有对应元素，否则不要设计"
        "账号锁定/验证码/XSS 弹出等页面不支持的场景。\n"
        "9. **params 键名必须与 POM actions 的 param_ref 完全一致**（如 username/password），"
        "不同值用同键（如 password 填错误值即可），不要自创键名。\n"
        "10. **断言文案精确匹配**：断言文本必须来自页面实际可见文案（错误提示 div 的"
        "文本如「请输入用户名」「用户名或密码错误」）；输入框占位符不是错误提示，"
        "不能作为失败断言；失败用例断言要落在具体错误文案可见。\n"
        "11. **覆盖均衡**：正常路径 + 关键异常路径（空字段/错误凭据）必须有；"
        "等价类与边界（如双空、超长输入）适度补充，3~8 行为宜。\n"
    )


def _load_tester_pro_md() -> str:
    """读 tester_pro.md（A3 评审员人设），缺失则用最小 fallback。"""
    content = _read_text_file(_repo_path("agent/skills/tester_pro.md"))
    if content:
        return content
    return (
        "# 角色：测试用例评审专家（A3）\n\n"
        "你是一位资深的测试设计评审员，负责对场景矩阵做质量门禁审查，"
        "找出覆盖缺口、断言缺失与数据设计问题。\n"
    )


def build_a3_instruction(matrix_draft: dict, pom_draft: dict) -> str:
    """构建 A3 评审阶段的完整指令。

    组成：tester_pro.md 人设 + matrix 草案 + POM 摘要 + 输出要求。
    输出契约：{verdict: pass|changes_needed, blocking_issues: [...],
    suggestions: [...], confidence: 0-1}
    """
    persona = _load_tester_pro_md()
    matrix_json = json.dumps(matrix_draft, ensure_ascii=False, indent=2)
    pom_json = json.dumps(pom_draft, ensure_ascii=False, indent=2)

    return (
        f"{persona}\n\n"
        f"## 任务\n\n"
        "请对以下测试用例矩阵草案做质量门禁评审（自动门）：\n"
        "- 检查场景是否覆盖正常路径与关键异常路径\n"
        "- 检查断言是否明确可执行\n"
        "- 检查参数化（param_ref）与 secret 标记是否正确\n"
        "- 找出阻塞性问题（覆盖缺口/断言缺失/数据错误）与非阻塞建议\n\n"
        "## POM 草案（评审参考）\n\n"
        "```json\n"
        f"{pom_json}\n"
        "```\n\n"
        "## 场景矩阵草案\n\n"
        "```json\n"
        f"{matrix_json}\n"
        "```\n\n"
        "## 输出要求\n\n"
        "只输出一个 ```json 围栏：\n"
        "{\n"
        '  "verdict": "pass" | "changes_needed",\n'
        '  "blocking_issues": ["覆盖缺口描述", ...],\n'
        '  "suggestions": ["非阻塞建议", ...],\n'
        '  "confidence": 0.0-1.0\n'
        "}\n"
        "不要任何其他文字。\n"
    )


def build_a4_instruction(matrix_draft: dict, pom_draft: dict) -> str:
    """构建 A4 生成阶段的完整指令。

    A4 是 DSH 的核心价值点：一个会话内闭环（生成->跑->读错->修，≤3 轮）。
    输入文件已由阶段服务写入工作区（matrix.json / pom.json / elements.json）：
     - 读取工作区根目录的 matrix.json、pom.json、elements.json
     - 生成 pytest 脚本 test_<module>.py（playwright sync API + expect 断言）
     - 用 `<repo>\venv\Scripts\python.exe -m pytest 脚本 -q` 运行
     - 失败则读错误修脚本，最多 3 轮
    输出契约：{status: pass|fail, script_file, rounds, summary, script_content, output_tail}
    """
    import sys as _sys

    py_exec = str(
        Path(settings.DSHOPS_REPO_ROOT) / "venv" / "Scripts" / "python.exe"
    )
    if _sys.platform != "win32":
        py_exec = "python3"
    matrix_json = json.dumps(matrix_draft, ensure_ascii=False, indent=2)

    return (
        "## 任务：生成并跑通 UI 测试脚本（会话内自修复闭环）\n\n"
        "工作区根目录已有三个输入文件：\n"
        "- `matrix.json`：场景矩阵（你要实现的用例）\n"
        "- `pom.json`：页面对象模型（元素与定位器）\n"
        "- `elements.json`：元素仓摘要（搜索优先复用）\n\n"
        "步骤：\n"
        "1. 读三个输入文件，理解页面结构（目标页可能需先启动：\n"
        "   若浏览器打不开 127.0.0.1:8000，先说明需先起后端服务）\n"
        "2. 生成 pytest 脚本 `test_<模块名>.py`，用 playwright sync API +\n"
        "   `from playwright.sync_api import sync_playwright, expect`，\n"
        "   按 matrix 的 rows 组织用例，参数化数据用 @pytest.mark.parametrize；\n"
        "   **浏览器启动必须用**：`p.chromium.launch(channel=\"chromium\", headless=True, "
        "args=[\"--ignore-certificate-errors\", \"--disable-blink-features=AutomationControlled\"])`\n"
        "   （用完整 chromium 新无头模式，不要用默认 headless-shell；"
        "若 chromium 通道不可用则改 channel=\"msedge\"；不要执行 playwright install 下载浏览器）\n"
        f"3. 用以下命令运行（headless）：\n"
        f"   `{py_exec} -m pytest test_<模块名>.py -q`\n"
        "4. 若失败：读报错→修脚本→重跑，最多 3 轮\n"
        "5. 完成后再把脚本内容与运行输出整理进最终 JSON\n\n"
        "## matrix.json 内容（供参考）\n\n"
        "```json\n"
        f"{matrix_json}\n"
        "```\n\n"
        "## 输出要求\n\n"
        "只输出一个 ```json 围栏：\n"
        "{\n"
        '  "status": "pass" | "fail",\n'
        '  "script_file": "test_xxx.py",\n'
        '  "rounds": 1-3,\n'
        '  "summary": "做了什么/修了什么",\n'
        '  "script_content": "脚本全文（转义为字符串）",\n'
        '  "output_tail": "pytest 输出末尾 200 字符"\n'
        "}\n"
        "不要任何其他文字。\n"
    )


def build_elements_summary(pom_draft: dict) -> str:
    """从 POM 草案生成元素仓摘要 JSON（A4 的 elements.json 输入）。"""
    return json.dumps(
        {
            "pages": pom_draft.get("pages", []),
            "elements": pom_draft.get("elements", []),
        },
        ensure_ascii=False,
        indent=2,
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
# NOTE: review/generate 条目在文件后部（run_review_stage/run_generate_stage 定义之后）再并入，
# 避免模块导入期的前向引用错误。


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


# ---------------------------------------------------------------------------
# A3 评审阶段
# ---------------------------------------------------------------------------

def run_review_stage(task_set: TaskSet, job: StageJob | None = None) -> TaskSet:
    """执行 A3 评审阶段（自动门）。

    守卫：仅 design_done 可进入。
    verdict=pass -> review_done；否则 -> failed（评审报告留档供人工处理）。
    """
    if job is None:
        if task_set.status != "design_done":
            raise ValueError(
                f"cannot run review stage from status {task_set.status!r}"
            )
        _transition(task_set, "reviewing")
        task_set.current_stage = "review"
        task_set.save(update_fields=["current_stage", "updated_at"])
        job = StageJob.objects.create(
            task_set=task_set,
            stage="review",
            status="running",
            started_at=timezone.now(),
        )

    try:
        # ---- 取 matrix 与 pom 草案 ------------------------------------------
        try:
            from apps.agent_runtime.models import ArtifactDraft  # type: ignore

            matrix_draft = (
                ArtifactDraft.objects.filter(
                    task_set_id=task_set.id, kind="matrix", valid=True
                )
                .order_by("-created_at")
                .first()
            )
            pom_draft = (
                ArtifactDraft.objects.filter(
                    task_set_id=task_set.id, kind="pom", valid=True
                )
                .order_by("-created_at")
                .first()
            )
        except Exception as exc:
            raise RuntimeError(f"cannot load drafts: {exc}")

        if matrix_draft is None:
            raise RuntimeError("no valid matrix draft found for review stage")
        if pom_draft is None:
            raise RuntimeError("no valid pom draft found for review stage")

        instruction = build_a3_instruction(matrix_draft.content, pom_draft.content)
        gateway = get_gateway()
        invocation = gateway.run_stage(
            "a3_review",
            instruction,
            task_set_id=task_set.id,
            recording_id=task_set.recording_id,
        )

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
            job.save(update_fields=["status", "finished_at", "detail", "updated_at"])
            _transition(task_set, "failed", error=error_msg)
            task_set.current_stage = ""
            task_set.save(update_fields=["current_stage", "updated_at"])
            return task_set

        report = invocation.parsed_json
        verdict = str(report.get("verdict", "changes_needed"))

        # 评审报告存 ArtifactDraft（kind=review），自动门判定
        try:
            from apps.agent_runtime.models import ArtifactDraft  # type: ignore

            draft = ArtifactDraft.objects.create(
                task_set_id=task_set.id,
                kind="review",
                content=report,
                schema_version=str(report.get("schema_version", "1.0.0-dev")),
                valid=True,
                invocation_id=getattr(invocation, "id", None),
                status="draft",
            )
        except Exception:
            draft = None

        job.finished_at = timezone.now()
        job.external_ref = f"invocation:{getattr(invocation, 'id', '')}"
        job.detail = {
            "verdict": verdict,
            "blocking_issues": report.get("blocking_issues", []),
            "suggestions": report.get("suggestions", []),
            "confidence": report.get("confidence"),
            "duration_ms": getattr(invocation, "duration_ms", None),
            "invocation_id": getattr(invocation, "id", None),
            "artifact_draft_id": getattr(draft, "id", None),
        }

        # 自动门：verdict=pass 放行；DSHOPS_REVIEW_AUTO_PASS=1 时 changes_needed 也放行
        # （阻塞问题仍留档在 review 报告里，供人工事后核对；默认严格模式）
        auto_pass = os.environ.get("DSHOPS_REVIEW_AUTO_PASS", "") == "1"
        if verdict == "pass" or auto_pass:
            if auto_pass and verdict != "pass":
                job.detail = {**job.detail, "auto_pass": True,
                              "auto_pass_note": "DSHOPS_REVIEW_AUTO_PASS=1 放行（问题留档）"}
            job.status = "success"
            job.save(
                update_fields=["status", "finished_at", "detail", "external_ref", "updated_at"]
            )
            _transition(task_set, "review_done")
            task_set.current_stage = ""
            task_set.save(update_fields=["current_stage", "updated_at"])
        else:
            job.status = "failed"
            job.save(
                update_fields=["status", "finished_at", "detail", "external_ref", "updated_at"]
            )
            issues = report.get("blocking_issues", [])
            _transition(
                task_set,
                "failed",
                error=f"A3 评审未通过: {'; '.join(issues) if issues else 'verdict != pass'}",
            )
            task_set.current_stage = ""
            task_set.save(update_fields=["current_stage", "updated_at"])

    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.finished_at = timezone.now()
        job.detail = {"error": str(exc), "stage": "review"}
        job.save(update_fields=["status", "finished_at", "detail", "updated_at"])
        task_set.error = str(exc)
        _transition(task_set, "failed", error=str(exc))
        task_set.current_stage = ""
        task_set.save(update_fields=["current_stage", "updated_at"])

    return task_set


# ---------------------------------------------------------------------------
# A4/A5 生成+自修复阶段（一个 DSH 会话内闭环）
# ---------------------------------------------------------------------------

def _last_valid_draft(task_set_id: int, kind: str):
    from apps.agent_runtime.models import ArtifactDraft  # type: ignore

    return (
        ArtifactDraft.objects.filter(task_set_id=task_set_id, kind=kind, valid=True)
        .order_by("-created_at")
        .first()
    )


def run_generate_stage(task_set: TaskSet, job: StageJob | None = None) -> TaskSet:
    """执行 A4/A5 生成+自修复阶段。

    守卫：仅 review_done 可进入。
    输入：matrix/pom 草案 + 元素仓摘要 注入工作区（input_files）；
    智能体在会话内生成脚本、运行、读错、自修（≤3 轮）；
    成功 -> generate_done + GeneratedRun(pass)；失败 -> failed + GeneratedRun(fail)。
    """
    if job is None:
        if task_set.status != "review_done":
            raise ValueError(
                f"cannot run generate stage from status {task_set.status!r}"
            )
        _transition(task_set, "generating")
        task_set.current_stage = "generate"
        task_set.save(update_fields=["current_stage", "updated_at"])
        job = StageJob.objects.create(
            task_set=task_set,
            stage="generate",
            status="running",
            started_at=timezone.now(),
        )

    generated = None
    try:
        matrix_draft = _last_valid_draft(task_set.id, "matrix")
        pom_draft = _last_valid_draft(task_set.id, "pom")
        if matrix_draft is None:
            raise RuntimeError("no valid matrix draft for generate stage")
        if pom_draft is None:
            raise RuntimeError("no valid pom draft for generate stage")

        instruction = build_a4_instruction(matrix_draft.content, pom_draft.content)
        input_files = {
            "matrix.json": json.dumps(matrix_draft.content, ensure_ascii=False, indent=2),
            "pom.json": json.dumps(pom_draft.content, ensure_ascii=False, indent=2),
            "elements.json": build_elements_summary(pom_draft.content),
        }
        gateway = get_gateway()
        invocation = gateway.run_stage(
            "a4_generate",
            instruction,
            task_set_id=task_set.id,
            recording_id=task_set.recording_id,
            input_files=input_files,
            timeout=600,  # A4 含生成+运行+自修（≤3 轮），放宽超时
        )

        if invocation.status != "success" or invocation.parsed_json is None:
            error_msg = (
                invocation.error
                or f"gateway status={invocation.status}, parsed_json=None"
            )
            job.status = "failed"
            job.finished_at = timezone.now()
            job.detail = {"error": error_msg, "invocation_id": getattr(invocation, "id", None)}
            job.save(update_fields=["status", "finished_at", "detail", "updated_at"])
            _transition(task_set, "failed", error=error_msg)
            task_set.current_stage = ""
            task_set.save(update_fields=["current_stage", "updated_at"])
            return task_set

        report = invocation.parsed_json
        status_ok = report.get("status") == "pass"
        script_file = str(report.get("script_file", ""))
        script_content = str(report.get("script_content", ""))
        rounds = int(report.get("rounds", 0) or 0)

        # 脚本兜底：报告没带全文时尝试从工作区读取
        if not script_content and invocation.workspace_path:
            ws = Path(invocation.workspace_path)
            if script_file and (ws / script_file).exists():
                script_content = (ws / script_file).read_text(encoding="utf-8")

        generated = GeneratedRun.objects.create(
            task_set_id=task_set.id,
            stage_job=job,
            invocation_id=getattr(invocation, "id", None),
            script_file=script_file,
            script_content=script_content,
            report=report,
            status="pass" if status_ok else "fail",
            rounds=rounds,
            duration_ms=getattr(invocation, "duration_ms", 0),
        )

        job.finished_at = timezone.now()
        job.external_ref = f"invocation:{getattr(invocation, 'id', '')}"
        job.detail = {
            "status": "pass" if status_ok else "fail",
            "script_file": script_file,
            "rounds": rounds,
            "summary": report.get("summary", ""),
            "output_tail": report.get("output_tail", ""),
            "duration_ms": getattr(invocation, "duration_ms", None),
            "generated_run_id": generated.id,
            "invocation_id": getattr(invocation, "id", None),
        }

        if status_ok:
            job.status = "success"
            job.save(
                update_fields=["status", "finished_at", "detail", "external_ref", "updated_at"]
            )
            _transition(task_set, "generate_done")
            task_set.current_stage = ""
            task_set.save(update_fields=["current_stage", "updated_at"])
        else:
            job.status = "failed"
            job.save(
                update_fields=["status", "finished_at", "detail", "external_ref", "updated_at"]
            )
            _transition(
                task_set,
                "failed",
                error=f"A4 生成未跑通（{rounds} 轮自修复后仍失败）: {report.get('summary', '')}",
            )
            task_set.current_stage = ""
            task_set.save(update_fields=["current_stage", "updated_at"])

    except Exception as exc:  # noqa: BLE001
        job.status = "failed"
        job.finished_at = timezone.now()
        job.detail = {"error": str(exc), "stage": "generate"}
        job.save(update_fields=["status", "finished_at", "detail", "updated_at"])
        task_set.error = str(exc)
        _transition(task_set, "failed", error=str(exc))
        task_set.current_stage = ""
        task_set.save(update_fields=["current_stage", "updated_at"])

    return task_set


# ---------------------------------------------------------------------------
# 流水线一键（replay -> extract -> design -> review -> generate）
# ---------------------------------------------------------------------------

# 阶段规格表：在全部阶段函数定义后补全（模块导入期无前向引用问题）
_STAGE_SPECS["review"] = {
    "fn": run_review_stage,
    "allowed": ("design_done",),
    "running": "reviewing",
    "current": "review",
    "job_stage": "review",
}
_STAGE_SPECS["generate"] = {
    "fn": run_generate_stage,
    "allowed": ("review_done",),
    "running": "generating",
    "current": "generate",
    "job_stage": "generate",
}


def run_pipeline(task_set: TaskSet) -> TaskSet:
    """按顺序执行完整流水线，任一步失败即停（StageJob 留痕）。

    幂等：已在 replay_done 之后的状态会跳过已完成阶段。
    """
    from .services import run_replay_stage  # type: ignore

    # 1. replay（若未完成）
    if task_set.status == "created":
        task_set = run_replay_stage(task_set)
        if task_set.status == "failed":
            return task_set

    # 2. extract
    if task_set.status in ("replay_done", "failed"):
        task_set = run_extract_stage(task_set)
        if task_set.status != "extract_done":
            return task_set

    # 3. design
    if task_set.status == "extract_done":
        task_set = run_design_stage(task_set)
        if task_set.status != "design_done":
            return task_set

    # 4. review
    if task_set.status == "design_done":
        task_set = run_review_stage(task_set)
        if task_set.status != "review_done":
            return task_set

    # 5. generate
    if task_set.status == "review_done":
        task_set = run_generate_stage(task_set)

    return task_set


def run_pipeline_async(task_set: TaskSet) -> TaskSet:
    """流水线一键（异步）：整条链在一个后台线程顺序执行。

    守卫失败/进行中抛 ValueError（409）。
    """
    if task_set.status not in ("created", "replay_done", "extract_done",
                               "design_done", "review_done", "failed"):
        raise ValueError(f"cannot run pipeline from status {task_set.status!r}")

    lock = _stage_lock(task_set.id)
    if not lock.acquire(blocking=False):
        raise ValueError(f"任务集 #{task_set.id} 已有阶段/流水线正在执行中")

    ts_pk = task_set.pk

    def _worker():
        try:
            from apps.tasksets.models import TaskSet as _TaskSet

            ts = _TaskSet.objects.get(pk=ts_pk)
            run_pipeline(ts)
        except Exception:  # run_pipeline 内部已兜底
            try:
                from apps.tasksets.models import TaskSet as _TaskSet

                ts = _TaskSet.objects.get(pk=ts_pk)
                ts.status = "failed"
                ts.error = "uncaught in pipeline worker"
                ts.save(update_fields=["status", "error", "updated_at"])
            except Exception:
                pass
        finally:
            lock.release()
            connections.close_all()

    threading.Thread(
        target=_worker, daemon=True, name=f"taskset-pipeline-{ts_pk}"
    ).start()
    return task_set
