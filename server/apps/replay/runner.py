"""回放执行器。

用 parser.extract_actions 的动作序列驱动自建精简 Playwright 执行器。
P1 子集：goto / click / fill / press / check / uncheck / select_option。
同步执行（HTTP 请求内跑），Playwright 相关 import 放函数内。
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import List, Dict, Optional


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _sha256_hex(file_path: str, length: int = 32) -> str:
    """计算文件 sha256，返回前 length 位十六进制。"""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:length]


def _build_locator(page, action: Dict):
    """根据动作的 locator_type + locator_value + name 重建 Playwright Locator。"""
    ltype = action.get("locator_type", "")
    lvalue = action.get("locator_value", "")
    name = action.get("name", "")

    if ltype == "role":
        kwargs = {}
        if name:
            kwargs["name"] = name
        return page.get_by_role(lvalue, **kwargs)
    elif ltype == "text":
        return page.get_by_text(lvalue)
    elif ltype == "label":
        return page.get_by_label(lvalue)
    elif ltype == "placeholder":
        return page.get_by_placeholder(lvalue)
    elif ltype == "testid":
        return page.get_by_test_id(lvalue)
    elif ltype == "css":
        return page.locator(lvalue)
    elif ltype == "alttext":
        return page.get_by_alt_text(lvalue)
    elif ltype == "title":
        return page.get_by_title(lvalue)
    else:
        raise ValueError(f"不支持的定位器类型: {ltype}")


def _resolve_page(pages: List, page_prefix: str, warnings: List[str]):
    """根据 page/page1/page2 前缀解析到对应的 page 对象。

    page -> 第 0 个
    page1 -> 第 1 个（若存在，否则用第 0 个并记 warning）
    """
    if page_prefix == "page":
        idx = 0
    elif page_prefix.startswith("page") and page_prefix[4:].isdigit():
        idx = int(page_prefix[4:])
    else:
        idx = 0

    if idx < len(pages):
        return pages[idx]
    # 越界 -> 用第一个 page，记 warning
    if pages:
        warnings.append(f"page 索引越界 ({page_prefix})，使用 page 0 代替")
        return pages[0]
    raise RuntimeError("没有可用的 page 对象")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def run_replay(recording, task_set_id: Optional[int] = None,
               headless: Optional[bool] = None,
               artifacts_dir: Optional[str] = None,
               replay_run: Optional["ReplayRun"] = None) -> "ReplayRun":
    """执行一次回放，返回已保存的 ReplayRun 对象。

    同步执行，耗时 30~90s。任何异常都会被捕获并写入 error 字段。
    Playwright 相关 import 在函数内部，失败时可降级。

    replay_run: 可选——传已存在实例时复用更新（P2 异步路径预建记录），
    否则内部新建。注意：跨线程使用时须在目标线程内重新 fetch。
    """
    # 延迟导入，避免启动时依赖
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            f"Playwright 未安装: {e}。请先运行 pip install playwright 并安装浏览器。"
        )

    from apps.replay.models import ReplayRun

    # 从录制中解析动作
    from apps.recorder.parser import parse_recording, extract_actions

    parse_result = parse_recording(recording.raw_content)
    actions = parse_result["actions"]
    parse_warnings = list(parse_result["warnings"])

    # 浏览器通道
    browser_channel = os.environ.get("DSHOPS_BROWSER_CHANNEL", "msedge").strip()
    if headless is None:
        headless = True

    # 产物目录
    if artifacts_dir:
        base_dir = Path(artifacts_dir)
    else:
        # 相对 server/ 的路径，server/artifacts/traces/
        base_dir = Path(__file__).resolve().parent.parent.parent / "artifacts" / "traces"
    base_dir.mkdir(parents=True, exist_ok=True)

    # 记录：传入实例则复用（异步路径预建），否则新建 running 记录
    if replay_run is not None:
        replay_run.recording = recording
        replay_run.task_set_id = task_set_id
        replay_run.status = "running"
        replay_run.steps_total = len(actions)
        replay_run.steps_passed = 0
        replay_run.error = ""
        replay_run.save(
            update_fields=[
                "recording", "task_set_id", "status", "steps_total",
                "steps_passed", "error", "updated_at",
            ]
        )
    else:
        replay_run = ReplayRun.objects.create(
            recording=recording,
            task_set_id=task_set_id,
            status="running",
            steps_total=len(actions),
            steps_passed=0,
        )

    trace_dir = base_dir / f"replay_{replay_run.pk}"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_path = str(trace_dir / "trace.zip")

    start_time = time.time()
    steps_passed = 0

    try:
        with sync_playwright() as p:
            # 启动浏览器
            launch_kwargs = {
                "headless": headless,
                "args": ["--ignore-certificate-errors"],
            }
            if browser_channel:
                launch_kwargs["channel"] = browser_channel

            browser = p.chromium.launch(**launch_kwargs)
            context = browser.new_context(ignore_https_errors=True)

            # 开 tracing
            context.tracing.start(snapshots=True, screenshots=True, sources=True)

            pages = [context.new_page()]
            runtime_warnings: List[str] = []

            try:
                for i, action in enumerate(actions):
                    atype = action.get("type", "")
                    raw = action.get("raw", "")

                    if atype == "popup":
                        # popup 标记动作跳过，popup 弹窗由 page.expect_popup 处理
                        # P1 简化：不做语义处理，仅忽略
                        steps_passed += 1
                        continue

                    if atype == "goto":
                        url = action.get("value", "")
                        if not url:
                            raise ValueError(f"步骤 {i}: goto 没有 URL")
                        pages[0].goto(url)
                        steps_passed += 1
                        continue

                    # 需要定位器的动作
                    # 从 raw 行里提取 page 前缀（原始记录）
                    import re
                    page_match = re.match(r'^\s*(page\d*)\.', raw)
                    page_prefix = page_match.group(1) if page_match else "page"
                    page_obj = _resolve_page(pages, page_prefix, runtime_warnings)

                    locator = _build_locator(page_obj, action)

                    if atype == "click":
                        locator.click()
                    elif atype == "fill":
                        locator.fill(action.get("value", ""))
                    elif atype == "press":
                        locator.press(action.get("value", "Enter"))
                    elif atype == "check":
                        locator.check()
                    elif atype == "uncheck":
                        locator.uncheck()
                    elif atype == "select_option":
                        locator.select_option(action.get("value", ""))
                    elif atype == "dblclick":
                        locator.dblclick()
                    else:
                        runtime_warnings.append(f"步骤 {i}: 未知动作类型 {atype}")
                        # 不中断，也算通过（warning 不视为失败）
                        steps_passed += 1
                        continue

                    steps_passed += 1

            finally:
                # 停止 tracing 并保存
                context.tracing.stop(path=trace_path)
                context.close()
                browser.close()

        # 计算 trace hash
        trace_hash = _sha256_hex(trace_path) if os.path.exists(trace_path) else ""

        duration_ms = int((time.time() - start_time) * 1000)

        # 合并 warnings
        all_warnings = parse_warnings + runtime_warnings

        replay_run.status = "success"
        replay_run.duration_ms = duration_ms
        replay_run.steps_passed = steps_passed
        replay_run.trace_path = trace_path
        replay_run.trace_hash = trace_hash
        replay_run.error = "\n".join(all_warnings) if all_warnings else ""
        replay_run.save()

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = f"步骤 {steps_passed} 失败: {type(e).__name__}: {str(e)}"

        # 尝试保存 trace（如果已生成）
        trace_hash = ""
        final_trace_path = ""
        if os.path.exists(trace_path):
            trace_hash = _sha256_hex(trace_path)
            final_trace_path = trace_path

        replay_run.status = "failed"
        replay_run.duration_ms = duration_ms
        replay_run.steps_passed = steps_passed
        replay_run.error = error_msg
        replay_run.trace_path = final_trace_path
        replay_run.trace_hash = trace_hash
        replay_run.save()

    return replay_run
