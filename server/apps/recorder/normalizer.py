"""
AI 脚本重组（P4 升级）：把录制脚本经 **POM 页面对象脚手架** 重组成标准稳定的 pytest 脚本。

- 脚手架（SCAFFOLD_TEMPLATE）：单文件、独立可运行——
  BasePage 基类（浏览器/定位方法，完全独立）+ 页面对象类（每步一方法，符合 POM 逻辑）
  + pytest fixtures（浏览器生命周期）+ 用例函数（POM 驱动调用）。
- mock 模式（DSHOPS_AGENT_MODE=mock）：本地按动作序列确定性生成 POM 脚本。
- real 模式：指令（脚手架全文 + 动作 JSON + raw 脚本）-> agent_runtime.gateway
  （stage 名 codegen_normalize，超时 300s）-> 剥 ```python 围栏。
- 结果写 Recording.normalized_content；失败追加 warnings。
- 重组成功后同步入库：apps.testcases.TestCase（source=ai_normalized），
  供"用例管理"页面查看（P4 需求：生成一份 pytest 脚本放入用例管理）。
"""
import json
import os
import re

from django.conf import settings

from .codegen import mark_normalize_done, mark_normalize_start, normalize_is_running


# ---------------------------------------------------------------------------
# POM 脚手架模板（旧平台 tests/conftest.py 的浏览器 fixture 思路 + POM 逻辑）
# ---------------------------------------------------------------------------

SCAFFOLD_TEMPLATE = '''# -*- coding: utf-8 -*-
"""<模块名> UI 自动化测试（POM 页面对象脚手架生成）

脚手架结构：
- BasePage：页面对象基类（浏览器上下文与定位方法，完全独立）
- <Xxx>Page：页面对象，每个操作一个独立方法（打开/定位/输入/点击，符合 POM 逻辑）
- fixtures：浏览器与页面生命周期（独立）
- test_*：pytest 用例，由页面对象方法驱动
"""
import os

import pytest
from playwright.sync_api import expect, sync_playwright

BASE_URL = "http://127.0.0.1:8001/api/demo/login/"
HEADLESS = os.environ.get("HEADLESS", "1") == "1"
BROWSER_CHANNEL = os.environ.get("DSHOPS_BROWSER_CHANNEL", "chromium")


# ============ POM 基类（完全独立） ============
class BasePage:
    """页面对象基类：封装浏览器定位与基础操作。"""

    def __init__(self, page):
        self.page = page

    def goto(self, url):
        self.page.goto(url)

    def by_role(self, role, name=None, exact=False):
        if name is None:
            return self.page.get_by_role(role)
        return self.page.get_by_role(role, name=name, exact=exact)

    def by_text(self, text):
        return self.page.get_by_text(text)

    def by_placeholder(self, text):
        return self.page.get_by_placeholder(text)

    def fill(self, locator, value):
        locator.fill(value)

    def click(self, locator):
        locator.click()

    def press(self, locator, key="Enter"):
        locator.press(key)


# ============ 页面对象（每步一个方法，符合 POM 逻辑） ============
class LoginPage(BasePage):
    """登录页页面对象：打开浏览器 / 定位输入框 / 输入内容 / 点击按钮 均独立成方法。"""

    def open(self):
        self.goto(BASE_URL)

    def fill_username(self, username):
        self.fill(self.by_role("textbox", name="请输入用户名"), username)

    def fill_password(self, password):
        self.fill(self.by_role("textbox", name="请输入密码"), password)

    def click_login(self):
        self.click(self.by_role("button", name="登录", exact=True))

    def error_message(self):
        return self.by_text("用户名或密码错误")

    def welcome_visible(self):
        return expect(self.by_text("欢迎回来")).to_be_visible(timeout=5000)


# ============ pytest fixtures（独立浏览器生命周期） ============
@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(
            channel=BROWSER_CHANNEL,
            headless=HEADLESS,
            args=["--ignore-certificate-errors", "--disable-blink-features=AutomationControlled"],
        )
        yield b
        b.close()


@pytest.fixture(scope="module")
def page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 720})
    pg = ctx.new_page()
    yield pg
    ctx.close()


# ============ 用例（POM 驱动） ============
def test_login_success(page):
    """正常路径：正确凭据登录成功。"""
    login = LoginPage(page)
    login.open()                       # 1 打开登录页
    login.fill_username("testadmin")   # 2 定位输入框并输入用户名
    login.fill_password("admin123456") # 3 输入密码
    login.click_login()                # 4 点击登录按钮
    login.welcome_visible()            # 断言：欢迎回来可见
'''


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _repo_path(relative: str):
    return settings.DSHOPS_REPO_ROOT / relative


def _read_text_file(path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _method_name(action: dict) -> str:
    """动作 -> POM 方法名：fill_<元素>/click_<元素>。"""
    atype = action.get("type", "")
    name = (action.get("name") or action.get("locator_value") or "target").strip()
    safe = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "", name) or "target"
    return f"{atype}_{safe}"


def _locator_expr(action: dict) -> str:
    """动作 -> BasePage 定位调用。"""
    ltype = action.get("locator_type", "role")
    value = action.get("locator_value", "button")
    name = action.get("name", "")
    if ltype == "text":
        return f'self.by_text("{name}")'
    if ltype == "placeholder":
        return f'self.by_placeholder("{name}")'
    if ltype == "css":
        return f'self.page.locator("{value}")'
    return f'self.by_role("{value}", name="{name}")'


def _mock_normalize(actions: list[dict]) -> str:
    """mock：把动作序列组装进 POM 脚手架，生成确定性脚本。"""
    base_url = ""
    method_lines: list[str] = []
    test_lines: list[str] = []
    used: set[str] = set()
    has_welcome = False

    for i, a in enumerate(actions):
        atype = a.get("type", "")
        value = a.get("value", "") or ""
        raw = a.get("raw", "") or ""
        if atype == "goto":
            if not base_url:
                base_url = value or "http://127.0.0.1:8001/api/demo/login/"
            continue
        if atype == "fill":
            m = _method_name(a)
            if m in used:
                m = f"{m}_{i}"
            used.add(m)
            method_lines.append(f"    def {m}(self, value):")
            method_lines.append(f"        self.fill({_locator_expr(a)}, value)")
            method_lines.append("")
            test_lines.append(f'    page_obj.{m}({json.dumps(value, ensure_ascii=False)})')
        elif atype == "click":
            m = _method_name(a)
            if m in used:
                m = f"{m}_{i}"
            used.add(m)
            method_lines.append(f"    def {m}(self):")
            method_lines.append(f"        self.click({_locator_expr(a)})")
            method_lines.append("")
            test_lines.append(f"    page_obj.{m}()")
        elif atype == "press":
            m = _method_name(a)
            if m in used:
                m = f"{m}_{i}"
            used.add(m)
            method_lines.append(f"    def {m}(self, key='{value or 'Enter'}'):")
            method_lines.append(f"        self.press({_locator_expr(a)}, key)")
            method_lines.append("")
            test_lines.append(f"    page_obj.{m}()")
        if "欢迎回来" in raw or "欢迎回来" in value:
            has_welcome = True

    if not base_url:
        base_url = "http://127.0.0.1:8001/api/demo/login/"

    # 页面对象类名（按 URL 推断）
    class_name = "LoginPage" if ("login" in base_url or "demo" in base_url) else "MainPage"
    if not method_lines:
        method_lines = ["    def open(self):", f"        self.goto(BASE_URL)", ""]

    body_methods = "\n".join(method_lines)
    test_body = "\n".join(test_lines)
    if has_welcome:
        test_body += '\n    expect(page.get_by_text("欢迎回来")).to_be_visible(timeout=5000)'

    script = SCAFFOLD_TEMPLATE.replace("LoginPage", class_name)
    script = script.replace(
        "    def open(self):\n"
        "        self.goto(BASE_URL)\n\n"
        "    def fill_username(self, username):\n"
        '        self.fill(self.by_role("textbox", name="请输入用户名"), username)\n\n'
        "    def fill_password(self, password):\n"
        '        self.fill(self.by_role("textbox", name="请输入密码"), password)\n\n'
        "    def click_login(self):\n"
        '        self.click(self.by_role("button", name="登录", exact=True))\n\n'
        "    def error_message(self):\n"
        '        return self.by_text("用户名或密码错误")\n\n'
        "    def welcome_visible(self):\n"
        '        return expect(self.by_text("欢迎回来")).to_be_visible(timeout=5000)',
        body_methods.rstrip("\n"),
    )
    script = script.replace(
        "    login = LoginPage(page)\n"
        "    login.open()                       # 1 打开登录页\n"
        '    login.fill_username("testadmin")   # 2 定位输入框并输入用户名\n'
        '    login.fill_password("admin123456") # 3 输入密码\n'
        "    login.click_login()                # 4 点击登录按钮\n"
        "    login.welcome_visible()            # 断言：欢迎回来可见",
        test_body,
    )
    return script


def normalize_recording(recording) -> None:
    """把录制重组为 POM pytest 脚本，写 recording.normalized_content；
    成功后将脚本入库 apps.testcases.TestCase（用例管理）。幂等可重入。"""
    mark_normalize_start(recording.id)
    try:
        from apps.recorder.parser import parse_recording

        result = parse_recording(recording.raw_content)
        actions = result["actions"]

        mode = os.environ.get("DSHOPS_AGENT_MODE", "real").lower()
        if mode == "mock":
            normalized = _mock_normalize(actions)
        else:
            # real：走 gateway（POM 脚手架指令）
            from apps.agent_runtime.gateway import AgentGateway

            skill = _read_text_file(_repo_path("agent/skills/pom-extraction/SKILL.md")) or ""
            actions_json = json.dumps(actions, ensure_ascii=False, indent=2)
            instruction = (
                f"{skill}\n\n"
                "## 任务\n\n"
                "以下是一个 **POM 页面对象脚手架模板** 与录制脚本。请把录制流程重组进脚手架，"
                "生成**标准稳定**的 pytest 脚本：\n"
                "- 保持 BasePage 基类与 fixtures 不变；\n"
                "- 把页面的每个操作拆成页面对象的独立方法（打开/定位/输入/点击，符合 POM 逻辑）；\n"
                "- 用例函数用页面对象方法驱动并补断言。\n\n"
                "## POM 脚手架模板\n\n"
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
                "只输出一个 ```python 围栏（完整可运行的 pytest 脚本，不要任何其他文字）。\n"
            )
            inv = AgentGateway().run_stage(
                "codegen_normalize", instruction, recording_id=recording.id, timeout=300
            )
            if inv.status != "success" or not inv.output_text:
                raise RuntimeError(inv.error or "gateway 未返回脚本")
            m = re.search(r"```python\s*(.*?)```", inv.output_text, re.DOTALL)
            normalized = m.group(1).strip() if m else inv.output_text.strip()

        recording.normalized_content = normalized
        recording.save(update_fields=["normalized_content", "updated_at"])

        # 同步入库用例管理（P4：生成一份 pytest 脚本放入用例管理）
        _sync_to_testcases(recording)
    except Exception as exc:  # noqa: BLE001
        warnings = list(recording.warnings or [])
        warnings.append(f"AI 重组失败: {type(exc).__name__}: {exc}")
        recording.warnings = warnings
        recording.save(update_fields=["warnings", "updated_at"])
    finally:
        mark_normalize_done(recording.id)


def _sync_to_testcases(recording) -> None:
    """把重组产物同步到用例管理（按 recording 幂等：重复重组只更新不新建）。"""
    try:
        from apps.testcases.models import TestCase

        content = recording.normalized_content or ""
        if not content.strip():
            return
        module = "demo" if "demo" in (recording.start_url or "") else "ui"
        TestCase.objects.update_or_create(
            recording_id=recording.id,
            defaults={
                "name": f"{recording.name}（POM 用例）",
                "content": content,
                "source": "ai_normalized",
                "status": "ready",
                "tags": [module],
            },
        )
    except Exception:
        pass  # 用例管理不可用时不影响重组主流程


def get_normalize_status(recording_id: int) -> str:
    """idle/running/done/failed（done/failed 从 normalized_content/warnings 推断）。"""
    if normalize_is_running(recording_id):
        return "running"
    return "idle"
