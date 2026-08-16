"""
RuntimeMgr 服务层。

所有业务逻辑集中在此模块，view 层仅做参数校验与响应封装。
设计原则：
- 所有子进程调用必须 try/except，不抛裸异常到 view
- 服务函数返回 dict 或 (bool, reason) 等结构化结果
- 外部依赖（subprocess、shutil、os）统一封装以便 mock 测试
"""
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import RuntimeInstance


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """返回仓库根目录。"""
    return Path(settings.DSHOPS_REPO_ROOT)


def _is_windows() -> bool:
    return sys.platform == "win32"


def _run_cmd(cmd, timeout=10, env=None, cwd=None):
    """安全地执行命令，返回 (returncode, stdout, stderr)。

    捕获 FileNotFoundError / TimeoutExpired / 其他异常，转换为非零返回码 + stderr 描述。
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            env=env,
            cwd=cwd,
            shell=_is_windows() and isinstance(cmd, str),
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except FileNotFoundError as exc:
        return 127, "", f"命令未找到: {exc}"
    except subprocess.TimeoutExpired as exc:
        return 124, "", f"命令超时 ({timeout}s): {exc}"
    except Exception as exc:  # noqa: BLE001 - 防御式编程，兜底所有异常
        return 1, "", f"执行异常: {exc}"


def _parse_dsh_version(stdout: str) -> str:
    """从 `dsh -V` / `dsh --version` 输出中提取版本号。

    常见格式：
    - "dsh/0.1.0-rc.6 win32-x64 node-v20.18.0"
    - "0.1.0-rc.6"
    """
    if not stdout:
        return ""
    # 先尝试 "dsh/<version>" 格式
    m = re.search(r"dsh[/\s]+v?([0-9][^\s]*)", stdout, re.IGNORECASE)
    if m:
        return m.group(1)
    # 再尝试行首直接是版本号
    m = re.search(r"^v?([0-9][^\s]*)", stdout.strip(), re.MULTILINE)
    if m:
        return m.group(1)
    return ""


def _parse_node_version(stdout: str) -> str:
    """从 `node -v` 输出中提取版本号（如 "v20.18.0"）。"""
    if not stdout:
        return ""
    m = re.search(r"v?([0-9][^\s]*)", stdout.strip())
    return m.group(1) if m else ""


def _list_profiles(home_dir: str) -> list:
    """扫描 DSH_HOME/profiles 下的一级子目录名列表。"""
    try:
        profiles_path = Path(home_dir) / "profiles"
        if not profiles_path.is_dir():
            return []
        return sorted(
            [p.name for p in profiles_path.iterdir() if p.is_dir() and not p.name.startswith(".")]
        )
    except OSError:
        return []


def _load_pinned_version() -> str:
    """从 contracts/version.json 读取 dsh_pinned 版本；读取失败返回空串。"""
    try:
        ver_path = _repo_root() / "contracts" / "version.json"
        if not ver_path.is_file():
            return ""
        with open(ver_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return str(data.get("dsh_pinned", ""))
    except (OSError, json.JSONDecodeError):
        return ""


# ---------------------------------------------------------------------------
# 探测服务
# ---------------------------------------------------------------------------

def detect_runtime(runtime_dir=None, home_dir=None):
    """探测 DSH 运行时环境，返回完整信息 dict。

    参数：
        runtime_dir: 可选，指定运行时目录（包含 node_modules 的目录）
        home_dir: 可选，指定 DSH_HOME 目录

    返回 dict 包含：
        - dsh_bin_path: dsh 二进制路径
        - runtime_dir: 运行时目录
        - home_dir: DSH_HOME 目录
        - home_dir_exists: home 目录是否存在
        - version: DSH 版本
        - version_raw: dsh -V 原始输出
        - node_version: Node.js 版本
        - profiles: profile 名称列表
        - pinned_version: 契约锁定版本
        - version_drift: 是否版本漂移
        - status: unknown/healthy/warning/error
        - status_detail: 状态说明
        - detect_source: 探测来源（local-runtime / global-which / not-found）
    """
    result = {
        "dsh_bin_path": "",
        "runtime_dir": "",
        "home_dir": "",
        "home_dir_exists": False,
        "version": "",
        "version_raw": "",
        "node_version": "",
        "profiles": [],
        "pinned_version": "",
        "version_drift": False,
        "status": "unknown",
        "status_detail": "",
        "detect_source": "not-found",
    }

    repo = _repo_root()

    # --- 定位 dsh 二进制 ---
    dsh_bin = ""
    detect_source = "not-found"

    # 1. 优先本地 runtime 目录
    if runtime_dir:
        candidate_dir = Path(runtime_dir)
    else:
        candidate_dir = repo / "agent" / "runtime"

    if candidate_dir.is_dir():
        bin_name = "dsh.cmd" if _is_windows() else "dsh"
        candidate = candidate_dir / "node_modules" / ".bin" / bin_name
        if candidate.is_file():
            dsh_bin = str(candidate)
            detect_source = "local-runtime"
            result["runtime_dir"] = str(candidate_dir)

    # 2. 回退全局
    if not dsh_bin:
        global_dsh = shutil.which("dsh")
        if global_dsh:
            dsh_bin = global_dsh
            detect_source = "global-which"
            # 全局模式下 runtime_dir 取 dsh 所在目录
            result["runtime_dir"] = str(Path(dsh_bin).parent)

    result["dsh_bin_path"] = dsh_bin
    result["detect_source"] = detect_source

    if not dsh_bin:
        result["status"] = "error"
        result["status_detail"] = "未找到 dsh 二进制（本地 runtime 与全局 PATH 均未找到）"
        return result

    # --- 获取 DSH 版本 ---
    ret, stdout, stderr = _run_cmd([dsh_bin, "-V"], timeout=10)
    result["version_raw"] = stdout
    if ret == 0:
        result["version"] = _parse_dsh_version(stdout)
    else:
        result["status"] = "error"
        result["status_detail"] = f"dsh -V 执行失败 (exit {ret}): {stderr[:200]}"
        # 继续尝试获取 node 版本，不提前返回

    # --- 获取 Node.js 版本 ---
    ret_node, stdout_node, _ = _run_cmd(["node", "-v"], timeout=5)
    if ret_node == 0:
        result["node_version"] = _parse_node_version(stdout_node)

    # --- DSH_HOME ---
    if home_dir:
        resolved_home = home_dir
    else:
        resolved_home = os.environ.get(
            "DSHOPS_DSH_HOME",
            str(repo / "agent" / "home"),
        )
    result["home_dir"] = str(resolved_home)
    result["home_dir_exists"] = Path(resolved_home).is_dir()

    # --- 扫描 profiles ---
    result["profiles"] = _list_profiles(resolved_home)

    # --- 版本漂移检查 ---
    pinned = _load_pinned_version()
    result["pinned_version"] = pinned
    if pinned and result["version"]:
        if pinned != result["version"]:
            result["version_drift"] = True
            if result["status"] not in ("error",):
                result["status"] = "warning"
                result["status_detail"] = (
                    f"版本漂移：实际 {result['version']}，契约要求 {pinned}"
                )
        elif result["status"] == "unknown":
            # 版本匹配且当前状态未知 => 健康
            result["status"] = "healthy"
    elif result["status"] == "unknown":
        result["status"] = "healthy"

    return result


def upsert_runtime_from_detect(detect_result, name=None, user=None):
    """根据 detect_runtime 的结果 upsert 一个 RuntimeInstance。

    - 若 name 未指定，自动生成：default-local / default-global
    - 返回 (instance, created)
    """
    if not name:
        src = detect_result.get("detect_source", "unknown")
        name = f"default-{src}"

    version = detect_result.get("version", "")
    status = detect_result.get("status", "unknown")
    notes = detect_result.get("status_detail", "")

    instance, created = RuntimeInstance.all_objects.update_or_create(
        name=name,
        defaults={
            "runtime_dir": detect_result.get("runtime_dir", ""),
            "dsh_bin_path": detect_result.get("dsh_bin_path", ""),
            "home_dir": detect_result.get("home_dir", ""),
            "version": version,
            "node_version": detect_result.get("node_version", ""),
            "status": status,
            "last_check_at": timezone.now(),
            "notes": notes,
            "is_deleted": False,
            "deleted_at": None,
        },
    )

    if user:
        if created:
            instance.created_by = user
        instance.updated_by = user
        instance.save(update_fields=["created_by", "updated_by"])

    return instance, created


# ---------------------------------------------------------------------------
# 健康检查
# ---------------------------------------------------------------------------

def health_check(instance):
    """对 RuntimeInstance 执行健康检查，更新实例状态并返回详情 dict。

    策略：
    - 如果 profiles 非空，取第一个 profile 跑 --dump-default-config
    - 否则直接 --dump-default-config（不带 profile）
    - exit 0 => healthy，否则 error
    - 任何异常 => error
    """
    detail = {
        "passed": False,
        "exit_code": None,
        "stdout": "",
        "stderr": "",
        "profile_used": "",
    }

    dsh_bin = instance.dsh_bin_path
    if not dsh_bin or not Path(dsh_bin).is_file():
        detail["stderr"] = "dsh 二进制不存在"
        instance.status = "error"
        instance.last_check_at = timezone.now()
        instance.notes = "健康检查失败：dsh 二进制不存在"
        instance.save(update_fields=["status", "last_check_at", "notes", "updated_at"])
        return detail

    home_dir = instance.home_dir or ""
    profiles = _list_profiles(home_dir)

    # 构造命令
    cmd = [dsh_bin]
    env = os.environ.copy()
    if home_dir:
        env["DSH_HOME"] = home_dir

    if profiles:
        profile = profiles[0]
        cmd += ["--profile", profile, "--dump-default-config"]
        detail["profile_used"] = profile
    else:
        # home 无 profile 时回退 headless：dsh 首次使用会从随附模板自动初始化；
        # 且 --dump-default-config 是 profile 启动项，不能脱离 --profile 单独使用
        cmd += ["--profile", "headless", "--dump-default-config"]
        detail["profile_used"] = "headless(auto-init)"

    ret, stdout, stderr = _run_cmd(cmd, timeout=20, env=env)
    detail["exit_code"] = ret
    detail["stdout"] = stdout[:500]
    detail["stderr"] = stderr[:500]

    if ret == 0:
        detail["passed"] = True
        instance.status = "healthy"
        instance.notes = ""
    else:
        instance.status = "error"
        stderr_summary = stderr[:200] if stderr else f"exit code {ret}"
        instance.notes = f"健康检查失败: {stderr_summary}"

    instance.last_check_at = timezone.now()
    instance.save(update_fields=["status", "last_check_at", "notes", "updated_at"])

    return detail


# ---------------------------------------------------------------------------
# 删除服务
# ---------------------------------------------------------------------------

def can_delete(instance):
    """删除前置检查 hook。

    返回 (bool, reason)。
    默认实现：始终允许。
    未来 TaskSet 等模块可通过 monkey-patch / signal 的方式注入额外校验。
    """
    return True, ""


def delete_runtime(instance, physical=False, delete_home=False, user=None):
    """删除 RuntimeInstance。

    - 默认软删（is_deleted=True）
    - physical=True 时物理删除 runtime_dir
    - delete_home=True 时额外删除 home_dir（需 physical 也为 True 才生效）
    - 写 AuditLog
    - 拒绝时返回 (False, reason)，成功返回 (True, '')
    """
    # 前置检查
    allowed, reason = can_delete(instance)
    if not allowed:
        return False, reason

    # 写审计日志（软删之前记，保留 id）
    from apps.core.models import AuditLog

    audit_detail = {
        "instance_id": instance.id,
        "instance_name": instance.name,
        "physical": physical,
        "delete_home": delete_home,
        "runtime_dir": instance.runtime_dir,
        "home_dir": instance.home_dir,
    }
    AuditLog.objects.create(
        action="runtime.delete",
        target=f"RuntimeInstance:{instance.id}:{instance.name}",
        detail=audit_detail,
        created_by=user,
    )

    # 物理删除文件（软删之前执行，失败则记录但不阻塞软删）
    if physical:
        errors = []
        if instance.runtime_dir and Path(instance.runtime_dir).exists():
            try:
                shutil.rmtree(instance.runtime_dir)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"runtime_dir 删除失败: {exc}")
        if delete_home and instance.home_dir and Path(instance.home_dir).exists():
            try:
                shutil.rmtree(instance.home_dir)
            except Exception as exc:  # noqa: BLE001
                errors.append(f"home_dir 删除失败: {exc}")
        if errors:
            instance.notes = "; ".join(errors)

    # 软删
    instance.is_deleted = True
    instance.deleted_at = timezone.now()
    if user:
        instance.updated_by = user
    instance.save(update_fields=["is_deleted", "deleted_at", "notes", "updated_at", "updated_by"])

    return True, ""


# ---------------------------------------------------------------------------
# 审计日志查询
# ---------------------------------------------------------------------------

def get_audit_logs_for_instance(instance):
    """获取指定实例的所有审计日志。"""
    from apps.core.models import AuditLog

    target_prefix = f"RuntimeInstance:{instance.id}:"
    return AuditLog.objects.filter(target__startswith=target_prefix).order_by("-created_at")
