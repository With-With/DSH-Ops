"""
AI 脚本重组（P4 #3.2）：把录制脚本经"默认脚手架"重组成标准稳定的 UI 自动化脚本。

- mock 模式（DSHOPS_AGENT_MODE=mock）：本地把动作序列套进脚手架模板，确定性产出
- real 模式：指令（pom-extraction SKILL + 脚手架全文 + 动作 JSON + raw 脚本）
  -> agent_runtime.gateway（stage 名 codegen_normalize，超时 300s）
- 结果写 Recording.normalized_content；失败追加 warnings
"""
import json
import os

from django.conf import settings

from .codegen import mark_normalize_done, mark_normalize_start, normalize_is_running

SCAFFOLD_TEMPLATE = '''# -*- coding: utf-8 -*-
"""UI 自动化脚本（DSH-Ops 标准脚手架重组产物）。

来源：codegen 录制 + AI 重组（P4 #3.2）。
"""
import os

import pytest
from playwright.sync_api import expect, sync_playwright

LOGIN_URL = "http://127.0.0.1:8001/api/demo/login/"
HEADLESS = os.environ.get("HEADLESS", "1") == "1"


@pytest.fixture(scope="module")
def browser_page():
    """标准浏览器夹具：完整 chromium 新无头模式。"""
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chromium",
            headless=HEADLESS,
            args=["--ignore-certificate-errors", "--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        yield page
        browser.close()


def test_main_flow(browser_page):
    """主流程用例（由录制动作重组而来）。"""
    page = browser_page
    page.goto(LOGIN_URL)
    # STEP: 0 goto
    # STEP: 1 click
    page.get_by_role("textbox", name="请输入用户名").click()
    # STEP: 2 fill
    page.get_by_role("textbox", name="请输入用户名").fill("testadmin")
    # STEP: 3 fill
    page.get_by_role("textbox", name="请输入密码").fill("admin123456")
    # STEP: 4 click
    page.get_by_role("button", name="登录", exact=True).click()
    # STEP: 5 assert
    expect(page.get_by_text("欢迎回来")).to_be_visible(timeout=5000)
'''

_MOCK_MAP = {
    "goto": "page.goto({value})",
    "click": "{loc}.click()",
    "fill": "{loc}.fill({value})",
    "press": "{loc}.press({value})",
    "check": "{loc}.check()",
    "uncheck": "{loc}.uncheck()",
    "select_option": "{loc}.select_option({value})",
}


def _repo_path(relative: str):
    return settings.DSHOPS_REPO_ROOT / relative


def _read_text_file(path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _locator_expr(action: dict, page_var: str = "page") -> str:
    ltype = action.get("locator_type", "role")
    name = action.get("name", "")
    value = action.get("locator_value", "button")
    if ltype == "role":
        return f'{page_var}.get_by_role("{value}", name="{name}")'
    if ltype == "text":
        return f'{page_var}.get_by_text("{name}")'
    if ltype == "placeholder":
        return f'{page_var}.get_by_placeholder("{name}")'
    if ltype == "css":
        return f'{page_var}.locator("{value}")'
    return f'{page_var}.get_by_role("{value}", name="{name}")'


def _mock_normalize(actions: list[dict]) -> str:
    """mock：把动作序列拼进脚手架的 test_main_flow 步骤区。"""
    body = []
    for i, a in enumerate(actions):
        atype = a.get("type", "")
        template = _MOCK_MAP.get(atype)
        body.append(f"    # STEP: {i} {atype}")
        if template is None:
            body.append(f"    # (未映射动作: {atype})")
            continue
        value = a.get("value", "")
        if "{loc}" in template:
            code = template.format(loc=_locator_expr(a), value=json.dumps(value, ensure_ascii=False))
        else:
            code = template.format(value=json.dumps(value, ensure_ascii=False))
        body.append("    " + code)
    steps = "\n".join(body)

    return SCAFFOLD_TEMPLATE.replace(
        "    # STEP: 0 goto\n"
        "    # STEP: 1 click\n"
        '    page.get_by_role("textbox", name="请输入用户名").click()\n'
        "    # STEP: 2 fill\n"
        '    page.get_by_role("textbox", name="请输入用户名").fill("testadmin")\n'
        "    # STEP: 3 fill\n"
        '    page.get_by_role("textbox", name="请输入密码").fill("admin123456")\n'
        "    # STEP: 4 click\n"
        '    page.get_by_role("button", name="登录", exact=True).click()\n'
        "    # STEP: 5 assert\n"
        '    expect(page.get_by_text("欢迎回来")).to_be_visible(timeout=5000)',
        steps,
    )


def normalize_recording(recording) -> None:
    """把录制重组为标准化脚本，写 recording.normalized_content。

    幂等：可重入（重复调用会重新生成）。进行中标志由调用方控制。
    """
    mark_normalize_start(recording.id)
    try:
        from apps.recorder.parser import parse_recording

        result = parse_recording(recording.raw_content)
        actions = result["actions"]

        mode = os.environ.get("DSHOPS_AGENT_MODE", "real").lower()
        if mode == "mock":
            normalized = _mock_normalize(actions)
            recording.normalized_content = normalized
            recording.save(update_fields=["normalized_content", "updated_at"])
            return

        # real：走 gateway
        from apps.agent_runtime.gateway import AgentGateway

        skill = _read_text_file(_repo_path("agent/skills/pom-extraction/SKILL.md")) or ""
        actions_json = json.dumps(actions, ensure_ascii=False, indent=2)
        instruction = (
            f"{skill}\n\n"
            "## 任务\n\n"
            "以下是平台默认脚手架模板与录制脚本。请把录制流程重组进脚手架，"
            "形成**标准稳定**的 UI 自动化脚本（补全定位器/等待/断言，"
            "保持 headless 与 channel=chromium 启动方式）。\n\n"
            "## 脚手架模板\n\n"
            "```python\n"
            f"{SCAFFOLD_TEMPLATE}\n"
            "```\n\n"
            "## 录制动作序列\n\n"
            "```json\n"
            f"{actions_json}\n"
            "```\n\n"
            "## 录制原始脚本\n\n"
            "```python\n"
            f"{recording.raw_content}\n"
            "```\n\n"
            "只输出一个 ```python 围栏（完整脚本，不要任何其他文字）。\n"
        )
        inv = AgentGateway().run_stage(
            "codegen_normalize", instruction, recording_id=recording.id, timeout=300
        )
        if inv.status != "success" or not inv.output_text:
            raise RuntimeError(inv.error or "gateway 未返回脚本")
        # 剥 ```python 围栏
        import re

        m = re.search(r"```python\s*(.*?)```", inv.output_text, re.DOTALL)
        normalized = m.group(1).strip() if m else inv.output_text.strip()
        recording.normalized_content = normalized
        recording.save(update_fields=["normalized_content", "updated_at"])
    except Exception as exc:  # noqa: BLE001
        warnings = list(recording.warnings or [])
        warnings.append(f"AI 重组失败: {type(exc).__name__}: {exc}")
        recording.warnings = warnings
        recording.save(update_fields=["warnings", "updated_at"])
    finally:
        mark_normalize_done(recording.id)


def get_normalize_status(recording_id: int) -> str:
    """idle/running/done/failed（done/failed 从 normalized_content/warnings 推断）。"""
    if normalize_is_running(recording_id):
        return "running"
    return "idle"
