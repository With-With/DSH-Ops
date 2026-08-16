"""
Agent Gateway：调用 DSH headless 模式执行 Agent 任务。

两种模式：
- 真实模式（默认）：subprocess 调用 `dsh --profile headless "<instruction>"`
- mock 模式：环境变量 DSHOPS_AGENT_MODE=mock 时，按 stage 返回 fixtures

所有调用都会写入 AgentInvocation 模型。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

from django.conf import settings

from .models import AgentInvocation


# ---------------------------------------------------------------------------
# JSON 提取
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```json\s*(.*?)```", re.DOTALL)


def extract_json(text: str) -> dict | None:
    """从 LLM 输出文本中提取 JSON 对象。

    优先级：
    1. ```json ... ``` 代码围栏（DOTALL 匹配）
    2. 首个配平的 {...} JSON 对象扫描
    3. 解析失败返回 None（不抛异常）
    """
    if not text:
        return None

    # 1. 代码围栏
    m = _FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass

    # 2. 首个配平的 {...}
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start : i + 1]
                try:
                    return json.loads(candidate)
                except (json.JSONDecodeError, ValueError):
                    start = -1  # 继续寻找下一个

    return None


# ---------------------------------------------------------------------------
# Agent Gateway
# ---------------------------------------------------------------------------

class AgentGateway:
    """DSH Agent 调用网关。

    用法：
        gw = AgentGateway()
        inv = gw.run_stage("pom_extract", "从...提取 POM", task_set_id=1)
    """

    def __init__(self):
        self.mode = os.environ.get("DSHOPS_AGENT_MODE", "real").lower()

    # ------------------------------------------------------------------
    # 路径 / 环境变量
    # ------------------------------------------------------------------

    @property
    def is_mock(self) -> bool:
        return self.mode == "mock"

    def _dsh_cmd(self) -> str:
        env_cmd = os.environ.get("DSHOPS_DSH_CMD", "")
        if env_cmd:
            return env_cmd
        # 默认：<repo>/agent/runtime/node_modules/.bin/dsh.cmd
        default = Path(settings.DSHOPS_REPO_ROOT) / "agent" / "runtime" / "node_modules" / ".bin" / "dsh.cmd"
        return str(default)

    def _timeout(self, override: float | None) -> float:
        if override is not None:
            return float(override)
        env_val = os.environ.get("DSHOPS_AGENT_TIMEOUT", "")
        if env_val:
            try:
                return float(env_val)
            except ValueError:
                pass
        return 300.0

    def _workspace_dir(self) -> Path:
        """创建独立工作区目录，返回路径。"""
        ws_root = Path(settings.DSHOPS_REPO_ROOT) / "server" / "artifacts" / "agent_ws"
        ws_dir = ws_root / str(uuid.uuid4())
        ws_dir.mkdir(parents=True, exist_ok=True)
        return ws_dir

    def _build_env(self) -> dict:
        env = os.environ.copy()
        agent_home = os.environ.get("DSHOPS_AGENT_HOME", "")
        if agent_home:
            env["DSH_HOME"] = agent_home
        return env

    # ------------------------------------------------------------------
    # Mock 模式
    # ------------------------------------------------------------------

    def _fixture_path(self, stage: str) -> Path | None:
        fixtures_dir = Path(__file__).parent / "fixtures"
        mapping = {
            "a1_extract": "mock_pom.json",      # tasksets.stages 实际阶段名
            "a2_design": "mock_matrix.json",
            "pom_extract": "mock_pom.json",     # 兼容旧名
            "matrix_design": "mock_matrix.json",
            "pom": "mock_pom.json",
            "matrix": "mock_matrix.json",
        }
        fname = mapping.get(stage)
        if fname:
            p = fixtures_dir / fname
            if p.exists():
                return p
        return None

    def _run_mock(self, stage: str, instruction: str, task_set_id, recording_id) -> AgentInvocation:
        """mock 模式：按 stage 返回 fixture。"""
        fixture = self._fixture_path(stage)
        if fixture:
            with open(fixture, "r", encoding="utf-8") as f:
                content = f.read()
            parsed = json.loads(content)
            output_text = content
            status = "success"
            error_msg = ""
        else:
            parsed = {"ack": True, "stage": stage}
            output_text = json.dumps(parsed, ensure_ascii=False)
            status = "success"
            error_msg = ""

        inv = AgentInvocation.objects.create(
            stage=stage,
            task_set_id=task_set_id,
            recording_id=recording_id,
            instruction=instruction,
            instruction_sha=hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
            output_text=output_text,
            parsed_json=parsed,
            status=status,
            exit_code=0,
            duration_ms=0,
            mock=True,
            error=error_msg,
        )
        return inv

    # ------------------------------------------------------------------
    # 真实模式
    # ------------------------------------------------------------------

    def _run_real(
        self,
        stage: str,
        instruction: str,
        task_set_id,
        recording_id,
        timeout_seconds: float,
    ) -> AgentInvocation:
        """真实模式：subprocess 调用 dsh --profile headless。

        指令传递：完整指令写入工作区根目录 task.md（避免 Windows cmd.exe
        命令行 8191 字符上限——A1 指令含完整 schema 常超 9KB），命令行只传
        短指令让智能体读取 task.md 后执行并仅输出 JSON 围栏。
        """
        dsh_cmd = self._dsh_cmd()
        ws_dir = self._workspace_dir()
        env = self._build_env()

        # 指令落盘 + 短命令行
        task_file = ws_dir / "task.md"
        task_file.write_text(instruction, encoding="utf-8")
        cli_instruction = (
            "请阅读本工作区根目录的 task.md 文件并严格按其执行。"
            "完成后只输出一个 ```json 代码块，不要任何其他文字。"
        )

        start = time.time()
        status = "success"
        exit_code = None
        stdout_text = ""
        stderr_text = ""
        error_msg = ""

        try:
            proc = subprocess.run(
                [dsh_cmd, "--profile", "headless", cli_instruction],
                cwd=str(ws_dir),
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout_seconds,
            )
            exit_code = proc.returncode
            stdout_text = proc.stdout or ""
            stderr_text = proc.stderr or ""

            if exit_code == 0:
                status = "success"
            else:
                status = "failed"
                # stderr 摘要（前 2000 字符，避免过长）
                summary = stderr_text.strip()
                if len(summary) > 2000:
                    summary = summary[:2000] + "\n...(truncated)"
                error_msg = f"exit_code={exit_code}; stderr={summary}"

        except subprocess.TimeoutExpired as e:
            status = "timeout"
            error_msg = f"timeout after {timeout_seconds}s"
            stdout_text = (e.stdout or "") if isinstance(e.stdout, str) else ""
            stderr_text = (e.stderr or "") if isinstance(e.stderr, str) else ""
            if isinstance(stdout_text, bytes):
                stdout_text = stdout_text.decode("utf-8", errors="replace")
            if isinstance(stderr_text, bytes):
                stderr_text = stderr_text.decode("utf-8", errors="replace")
        except Exception as e:
            status = "error"
            error_msg = f"{type(e).__name__}: {e}"

        duration_ms = int((time.time() - start) * 1000)

        # 解析 JSON
        parsed = extract_json(stdout_text)

        inv = AgentInvocation.objects.create(
            stage=stage,
            task_set_id=task_set_id,
            recording_id=recording_id,
            instruction=instruction,
            instruction_sha=hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
            output_text=stdout_text,
            parsed_json=parsed,
            status=status,
            exit_code=exit_code,
            duration_ms=duration_ms,
            mock=False,
            error=error_msg,
        )
        return inv

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def run_stage(
        self,
        stage: str,
        instruction: str,
        task_set_id: int | None = None,
        recording_id: int | None = None,
        timeout: float | None = None,
    ) -> AgentInvocation:
        """执行一个 Agent 阶段任务，返回 AgentInvocation 记录。

        Args:
            stage: 阶段名（如 pom_extract / matrix_design）
            instruction: 给 DSH agent 的指令文本
            task_set_id: 关联任务集 ID（可选）
            recording_id: 关联录制 ID（可选）
            timeout: 超时秒数（可选，默认读环境变量或 300s）

        Returns:
            AgentInvocation 实例（已入库）
        """
        if self.is_mock:
            return self._run_mock(stage, instruction, task_set_id, recording_id)

        timeout_s = self._timeout(timeout)
        return self._run_real(stage, instruction, task_set_id, recording_id, timeout_s)
