"""
codegen 录制会话管理（P4 #3）：playwright codegen 浏览器交互录制。

- start: 起子进程 `python -m playwright codegen --target python -o <file> <url>`（DETACHED）
- status: 会话状态查询
- stop: 杀进程树，轮询产物文件落盘，创建 Recording（复用既有 parse）
"""
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from django.conf import settings
from django.utils import timezone

_sessions: dict[str, dict] = {}
_sessions_lock = threading.Lock()


def _codegen_root() -> Path:
    return Path(settings.DSHOPS_REPO_ROOT) / "server" / "artifacts" / "codegen"


def start_session(name: str = "", start_url: str = "") -> dict:
    """启动 codegen 会话，返回会话信息。"""
    session_id = str(uuid.uuid4())[:8]
    if not start_url:
        start_url = "http://127.0.0.1:8001/api/demo/login/"

    session_dir = _codegen_root() / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    output_file = session_dir / "raw_script.py"

    cmd = [
        sys.executable, "-m", "playwright", "codegen",
        "--target", "python",
        "--browser", "chromium",
        "--output", str(output_file),
        start_url,
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(session_dir),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )

    session = {
        "session_id": session_id,
        "name": name or f"codegen-{timezone.now().strftime('%Y%m%d-%H%M%S')}",
        "start_url": start_url,
        "started_at": timezone.now().isoformat(),
        "pid": proc.pid,
        "output_file": str(output_file),
        "stopped": False,
    }
    with _sessions_lock:
        _sessions[session_id] = session
    return session


def get_status() -> dict:
    """当前是否有活跃会话。"""
    with _sessions_lock:
        active = [s for s in _sessions.values() if not s["stopped"]]
        if not active:
            return {"active": False}
        s = active[-1]
        return {
            "active": True,
            "session_id": s["session_id"],
            "name": s["name"],
            "start_url": s["start_url"],
            "started_at": s["started_at"],
            "pid": s["pid"],
        }


def _kill_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(pid)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    else:
        os.kill(pid, 9)


def stop_session(session_id: str, auto_analyze: bool = False) -> dict:
    """结束录制：杀进程、等产物落盘、建 Recording（可选触发 AI 重组）。"""
    with _sessions_lock:
        session = _sessions.get(session_id)
    if session is None:
        raise ValueError("会话不存在")

    session["stopped"] = True
    if session.get("pid"):
        try:
            _kill_tree(session["pid"])
        except Exception:
            pass

    # 轮询产物文件落盘（codegen 关闭后写文件，最多 10s）
    output_file = Path(session["output_file"])
    raw_content = ""
    for _ in range(20):
        if output_file.exists() and output_file.stat().st_size > 0:
            raw_content = output_file.read_text(encoding="utf-8", errors="replace")
            break
        time.sleep(0.5)

    if not raw_content.strip():
        return {
            "ok": False,
            "detail": "录制产物为空：请在浏览器中操作后再结束录制",
            "recording_id": None,
        }

    from apps.recorder.models import Recording
    from apps.recorder.parser import parse_recording

    # 落库前解析：填充语言/框架/起始URL/定位器数/动作数/警告（P4 #2 修复：
    # 此前直接 create 导致统计字段全为 0）
    try:
        parse_result = parse_recording(raw_content)
    except Exception:
        parse_result = {
            "language": "python", "framework": "playwright", "start_url": "",
            "locators_count": 0, "actions_count": 0,
            "normalized_content": "", "warnings": ["脚本解析失败"],
            "actions": [],
        }

    recording = Recording.objects.create(
        name=session.get("name") or f"codegen-{session_id}",
        raw_content=raw_content,
        language=parse_result["language"],
        framework=parse_result["framework"],
        start_url=parse_result["start_url"],
        normalized_content=parse_result["normalized_content"],
        locators_count=parse_result["locators_count"],
        actions_count=parse_result["actions_count"],
        warnings=parse_result["warnings"],
    )

    result = {
        "ok": True,
        "recording_id": recording.id,
        "name": recording.name,
        "actions_count": recording.actions_count,
        "auto_analyze": bool(auto_analyze),
    }

    if auto_analyze:
        from .normalizer import normalize_recording

        threading.Thread(
            target=_safe_normalize,
            args=(recording.id,),
            daemon=True,
            name=f"codegen-normalize-{recording.id}",
        ).start()

    return result


def _safe_normalize(recording_id: int) -> None:
    from django.db import connections

    from apps.recorder.models import Recording

    try:
        rec = Recording.objects.get(pk=recording_id)
        normalize_recording(rec)
    except Exception:
        pass
    finally:
        connections.close_all()


# normalize 运行状态（模块级，避免改模型）
_normalize_running: set[int] = set()
_normalize_lock = threading.Lock()


def mark_normalize_start(recording_id: int) -> None:
    with _normalize_lock:
        _normalize_running.add(recording_id)


def mark_normalize_done(recording_id: int) -> None:
    with _normalize_lock:
        _normalize_running.discard(recording_id)


def normalize_is_running(recording_id: int) -> bool:
    with _normalize_lock:
        return recording_id in _normalize_running
