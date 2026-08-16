"""
组件管理（P4 #1）：playwright / selenium / 浏览器(Edge/Chrome) 的检测与安装/删除。

- 检测基于：pip 包 find_spec、playwright 浏览器通道、Windows 注册表/常见路径
- 安装/删除走线程（pip / playwright install chromium），只允许 pip 可管理项；
  系统级 Edge/Chrome 不可安装/删除，只提供指引
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import threading

from django.conf import settings


# ---------------------------------------------------------------------------
# 检测
# ---------------------------------------------------------------------------

def _venv_python() -> str:
    return str(
        (settings.BASE_DIR.parent / "venv" / "Scripts" / "python.exe")
        if sys.platform == "win32"
        else (settings.BASE_DIR.parent / "venv" / "bin" / "python")
    )


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _playwright_browser_available(channel: str) -> bool:
    """检查 playwright 某浏览器通道是否已安装可启动。"""
    if not _has_module("playwright"):
        return False
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            if channel == "chromium":
                # channel=None 表示默认 chromium；msedge/chrome/firefox 用 channel 名
                launch_kwargs = {"headless": True}
            else:
                launch_kwargs = {"headless": True, "channel": channel}
            b = p.chromium.launch(**launch_kwargs)
            b.close()
        return True
    except Exception:
        return False


def _installed_version(module: str) -> str:
    try:
        from importlib.metadata import version

        return version(module)
    except Exception:
        return ""


def _detect_browser(browser: str) -> dict:
    """系统浏览器检测：注册表 App Paths + 常见安装路径。"""
    candidates = []
    if sys.platform == "win32":
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                rf"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\{browser}.exe",
            )
            try:
                path, _ = winreg.QueryValueEx(key, None)
                candidates.append(path)
            finally:
                winreg.CloseKey(key)
        except OSError:
            pass
    common = {
        "msedge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ],
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ],
    }.get(browser, [])
    for c in common:
        if os.path.exists(c):
            candidates.append(c)
    if not candidates:
        which = shutil.which(f"{browser}.exe") or shutil.which(browser)
        if which:
            candidates.append(which)
    return {
        "installed": bool(candidates),
        "path": candidates[0] if candidates else "",
    }


def detect_components() -> list[dict]:
    """返回全部组件状态（供 GET /runtimes/components/）。"""
    items = []

    # 1. playwright
    pw_installed = _has_module("playwright")
    items.append({
        "key": "playwright",
        "name": "Playwright",
        "kind": "pip",
        "installed": pw_installed,
        "version": _installed_version("playwright") if pw_installed else "",
        "detail": "浏览器自动化框架（含录制/回放/视频）",
        "actions": ["install", "delete"] if pw_installed else ["install"],
        "install_hint": "pip install playwright + playwright install chromium",
    })

    # 2. selenium
    se_installed = _has_module("selenium")
    items.append({
        "key": "selenium",
        "name": "Selenium",
        "kind": "pip",
        "installed": se_installed,
        "version": _installed_version("selenium") if se_installed else "",
        "detail": "Web 自动化框架（兼容旧脚本）",
        "actions": ["install", "delete"] if se_installed else ["install"],
        "install_hint": "pip install selenium",
    })

    # 3. 系统浏览器 Edge / Chrome
    for browser, label in (("msedge", "Microsoft Edge"), ("chrome", "Google Chrome")):
        info = _detect_browser(browser)
        items.append({
            "key": f"browser-{browser}",
            "name": label,
            "kind": "system",
            "installed": info["installed"],
            "version": "",
            "detail": f"系统浏览器（{info['path'] or '未检测到'}）",
            "actions": [],
            "install_hint": "系统级组件，请通过系统安装程序管理",
        })

    # 4. playwright 浏览器通道 chromium
    items.append({
        "key": "pw-chromium",
        "name": "Chromium（Playwright）",
        "kind": "pw-browser",
        "installed": _playwright_browser_available("chromium"),
        "version": "",
        "detail": "Playwright 完整浏览器（新无头模式，A4 生成脚本推荐）",
        "actions": ["install"] if not _playwright_browser_available("chromium") else ["delete"],
        "install_hint": "playwright install chromium（国内走 npmmirror 镜像）",
    })

    return items


# ---------------------------------------------------------------------------
# 安装 / 删除（线程执行）
# ---------------------------------------------------------------------------

_running_tasks: dict[str, dict] = {}
_tasks_lock = threading.Lock()


def is_task_running(key: str) -> bool:
    with _tasks_lock:
        task = _running_tasks.get(key)
        return bool(task and task.get("running"))


def list_running_tasks() -> dict:
    with _tasks_lock:
        return {k: v for k, v in _running_tasks.items()}


def _mark(key: str, op: str, running: bool, detail: str = "") -> None:
    with _tasks_lock:
        _running_tasks[key] = {
            "op": op, "running": running, "started_at": None, "detail": detail,
        }


def _run_in_thread(key: str, op: str, func) -> None:
    import time as _time

    from django.utils import timezone

    _mark(key, op, True, "执行中")
    with _tasks_lock:
        _running_tasks[key]["started_at"] = timezone.now().isoformat()

    def _worker():
        try:
            func()
            _mark(key, op, False, "完成")
        except Exception as exc:  # noqa: BLE001
            _mark(key, op, False, f"失败: {type(exc).__name__}: {exc}")
        finally:
            from django.db import connections

            connections.close_all()

    threading.Thread(target=_worker, daemon=True, name=f"runtime-component-{key}").start()


def _pip_install(pkg: str) -> None:
    env = os.environ.copy()
    env.setdefault(
        "PLAYWRIGHT_DOWNLOAD_HOST", "https://npmmirror.com/mirrors/playwright/"
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "install", pkg, "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"],
        env=env, check=True, timeout=900,
    )


def _pip_uninstall(pkg: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", pkg],
        check=True, timeout=300,
    )


def install_component(key: str) -> str:
    """触发安装（校验合法 key），返回安装方式说明。"""
    if key == "playwright":
        _run_in_thread(key, "install", lambda: _pip_install("playwright"))
        return "pip install playwright"
    if key == "selenium":
        _run_in_thread(key, "install", lambda: _pip_install("selenium"))
        return "pip install selenium"
    if key == "pw-chromium":
        _run_in_thread(
            key, "install",
            lambda: subprocess.run(
                [
                    sys.executable, "-m", "playwright", "install", "chromium",
                ],
                env=os.environ
                | {"PLAYWRIGHT_DOWNLOAD_HOST": "https://npmmirror.com/mirrors/playwright/"},
                check=True, timeout=1800,
            ),
        )
        return "playwright install chromium"
    raise ValueError(f"组件 {key} 不支持安装")


def delete_component(key: str) -> str:
    """触发删除，返回删除方式说明。"""
    if key == "playwright":
        _run_in_thread(key, "delete", lambda: _pip_uninstall("playwright"))
        return "pip uninstall playwright"
    if key == "selenium":
        _run_in_thread(key, "delete", lambda: _pip_uninstall("selenium"))
        return "pip uninstall selenium"
    if key == "pw-chromium":
        _run_in_thread(
            key, "delete",
            lambda: subprocess.run(
                [sys.executable, "-m", "playwright", "uninstall", "--all"],
                check=True, timeout=600,
            ),
        )
        return "playwright uninstall"
    raise ValueError(f"组件 {key} 不支持删除（系统级组件请用系统安装程序）")
