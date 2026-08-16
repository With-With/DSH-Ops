"""
tasksets 单元测试：
- 状态机合法 / 非法转换
- create_task_set
- run_replay_stage 成功 / 失败 / 模块不可用（mock sys.modules）
- API 列表 / 创建 / 详情
"""
import sys
from types import ModuleType

from django.test import TestCase
from rest_framework.test import APIClient

from .models import StageJob, TaskSet
from .services import allowed_transitions, can_transition, create_task_set, run_replay_stage


class StateMachineTransitionTests(TestCase):
    def test_allowed_transitions_dict_complete(self):
        """所有出现的状态都在转换表中。"""
        all_statuses = {s for s, _ in TaskSet.STATUS_CHOICES}
        self.assertEqual(set(allowed_transitions.keys()), all_statuses)

    def test_legal_transitions(self):
        legal = [
            ("created", "replaying"),
            ("created", "failed"),
            ("replaying", "replay_done"),
            ("replaying", "failed"),
            ("replay_done", "failed"),
        ]
        for cur, nxt in legal:
            self.assertTrue(
                can_transition(cur, nxt),
                f"{cur} -> {nxt} should be legal",
            )

    def test_illegal_transitions(self):
        illegal = [
            ("replay_done", "replaying"),
            ("failed", "replaying"),
            ("created", "replay_done"),
            ("replay_done", "created"),
        ]
        for cur, nxt in illegal:
            with self.assertRaises(ValueError, msg=f"{cur} -> {nxt} should fail"):
                can_transition(cur, nxt)

    def test_unknown_current_status(self):
        with self.assertRaises(ValueError):
            can_transition("bogus", "failed")

    def test_unknown_target_status(self):
        with self.assertRaises(ValueError):
            can_transition("created", "bogus")

    def test_failed_retry_path(self):
        """P2: failed 后可重入 extracting（重试路径），其余目标非法。"""
        self.assertEqual(allowed_transitions["failed"], {"extracting"})
        self.assertTrue(can_transition("failed", "extracting"))
        for target in ["created", "replaying", "replay_done", "extract_done", "designing", "design_done"]:
            with self.assertRaises(ValueError, msg=f"failed -> {target} should fail"):
                can_transition("failed", target)


class CreateTaskSetTests(TestCase):
    def test_create_basic(self):
        ts = create_task_set("测试任务集", recording_id=42)
        self.assertEqual(ts.status, "created")
        self.assertEqual(ts.recording_id, 42)
        self.assertEqual(ts.name, "测试任务集")
        self.assertIsNotNone(ts.correlation_uuid)
        self.assertEqual(ts.current_stage, "")


class RunReplayStageMockTests(TestCase):
    """用 mock 模块（替换 sys.modules）测试 replay 各种分支。"""

    def setUp(self):
        self.ts = create_task_set("mock 测试", recording_id=1)
        # 保存原来的模块引用，测试后恢复
        self._saved_modules = {}

    def tearDown(self):
        # 恢复被替换的模块
        for key, value in self._saved_modules.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value

    def _install_fake_modules(self, run_replay_impl, recording_exists=True):
        """安装假的 replay.runner 和 recorder.models 模块。"""
        # fake replay.runner
        fake_runner = ModuleType("apps.replay.runner")
        fake_runner.run_replay = run_replay_impl
        self._saved_modules["apps.replay.runner"] = sys.modules.get(
            "apps.replay.runner"
        )
        sys.modules["apps.replay.runner"] = fake_runner

        # fake recorder.models
        fake_recorder = ModuleType("apps.recorder.models")

        class FakeRecording:
            pk = 1
            id = 1
            raw_content = "fake content"

            @staticmethod
            def get(pk=None, **kw):
                if not recording_exists:
                    from django.core.exceptions import ObjectDoesNotExist
                    raise ObjectDoesNotExist("not found")
                return FakeRecording()

        objects = type("Objects", (), {"get": FakeRecording.get})()
        FakeRecording.objects = objects

        fake_recorder.Recording = FakeRecording
        self._saved_modules["apps.recorder.models"] = sys.modules.get(
            "apps.recorder.models"
        )
        sys.modules["apps.recorder.models"] = fake_recorder

    def test_replay_success_dict(self):
        """replay 返回 dict → success。"""

        def fake_run(recording, task_set_id=None, headless=None):
            return {"id": 55, "duration": 30.0, "steps": 10, "trace_hash": "hash-xyz"}

        self._install_fake_modules(fake_run)

        ts = run_replay_stage(self.ts)
        self.assertEqual(ts.status, "replay_done")
        self.assertEqual(ts.error, "")

        job = StageJob.objects.get(task_set=ts, stage="replay")
        self.assertEqual(job.status, "success")
        self.assertEqual(job.external_ref, "replay:55")
        self.assertEqual(job.detail["steps"], 10)
        self.assertEqual(job.detail["trace_hash"], "hash-xyz")
        self.assertIsNotNone(job.finished_at)

    def test_replay_success_with_object(self):
        """replay 返回模型实例（带 id 属性）→ success。"""

        class FakeReplayResult:
            id = 77
            duration = 12.5
            steps = 5
            trace_hash = "abc"

        def fake_run(recording, task_set_id=None, headless=None):
            return FakeReplayResult()

        self._install_fake_modules(fake_run)

        ts = run_replay_stage(self.ts)
        self.assertEqual(ts.status, "replay_done")
        job = StageJob.objects.get(task_set=ts, stage="replay")
        self.assertEqual(job.status, "success")
        self.assertEqual(job.external_ref, "replay:77")

    def test_replay_runtime_exception(self):
        """replay 运行时抛异常 → failed（不是 500，而是优雅捕获）。"""

        def fake_run(recording, task_set_id=None, headless=None):
            raise RuntimeError("browser crashed")

        self._install_fake_modules(fake_run)

        ts = run_replay_stage(self.ts)
        self.assertEqual(ts.status, "failed")
        self.assertIn("browser crashed", ts.error)

        job = StageJob.objects.get(task_set=ts, stage="replay")
        self.assertEqual(job.status, "failed")
        self.assertIn("browser crashed", job.detail["error"])

    def test_replay_module_unavailable(self):
        """replay.runner 模块不存在 → 优雅降级为 service unavailable。

        通过把 sys.modules 中对应 key 设为 None 来模拟 ImportError。
        """
        # 保存并移除
        self._saved_modules["apps.replay.runner"] = sys.modules.get(
            "apps.replay.runner"
        )
        sys.modules.pop("apps.replay.runner", None)
        # 确保 import 会失败：用一个会触发 ImportError 的钩子
        # 更简单：直接给一个不存在的模块路径
        # 我们用 patch 的方式：用 importlib 拦截
        import builtins

        original_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "apps.replay.runner" or (
                isinstance(name, str) and name.startswith("apps.replay.runner")
            ):
                raise ModuleNotFoundError("No module named 'apps.replay.runner'")
            return original_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            ts = run_replay_stage(self.ts)
            self.assertEqual(ts.status, "failed")
            self.assertIn("replay service unavailable", ts.error)

            job = StageJob.objects.get(task_set=ts, stage="replay")
            self.assertEqual(job.status, "failed")
            self.assertEqual(job.detail.get("error"), "replay service unavailable")
            self.assertIsNotNone(job.finished_at)
        finally:
            builtins.__import__ = original_import

    def test_illegal_transition_from_replay_done(self):
        """已经是 replay_done 再跑 replay 应该被状态机守卫拒绝。"""
        self.ts.status = "replay_done"
        self.ts.save()
        with self.assertRaises(ValueError):
            run_replay_stage(self.ts)

    def test_illegal_transition_from_failed(self):
        """已经 failed 再跑 replay 也应被拒。"""
        self.ts.status = "failed"
        self.ts.save()
        with self.assertRaises(ValueError):
            run_replay_stage(self.ts)


class TaskSetApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ts = create_task_set("API 测试", recording_id=7)

    def test_list_tasksets(self):
        resp = self.client.get("/api/tasksets/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["recording_id"], 7)
        self.assertEqual(data["results"][0]["status"], "created")

    def test_retrieve_taskset_with_stage_jobs(self):
        resp = self.client.get(f"/api/tasksets/{self.ts.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("stage_jobs", data)
        self.assertIsInstance(data["stage_jobs"], list)

    def test_create_taskset_api_no_500(self):
        """创建任务集 API：不论 replay 是否可用，都不应返回 500。

        由于环境里 replay 模块存在但 playwright 不一定装，
        实际会走到 runtime exception 分支，状态为 failed。
        我们只验证 HTTP 201 + 有 stage_jobs + 状态非 created（说明跑了）。
        """
        resp = self.client.post(
            "/api/tasksets/",
            {"name": "新建任务", "recording_id": 99},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)  # 不抛 500
        data = resp.json()
        self.assertEqual(data["name"], "新建任务")
        self.assertNotEqual(data["status"], "created")  # 说明已经走过 replay
        self.assertTrue(len(data["stage_jobs"]) >= 1)
        # stage_jobs 里有 replay 阶段
        stages = [j["stage"] for j in data["stage_jobs"]]
        self.assertIn("replay", stages)


# ---------------------------------------------------------------------------
# P3：A3 评审 / A4 生成 / 流水线
# ---------------------------------------------------------------------------

def _make_drafts(task_set_id: int):
    """给任务集造 pom + matrix 有效草案（供 review/generate 消费）。"""
    from apps.agent_runtime.models import ArtifactDraft

    ArtifactDraft.objects.create(
        task_set_id=task_set_id,
        kind="pom",
        content={"schema_version": "1.0.0-dev", "pages": [], "elements": [],
                 "actions": [], "params": [], "confidence": 0.9, "source": {}},
        schema_version="1.0.0-dev",
        valid=True,
        status="draft",
    )
    ArtifactDraft.objects.create(
        task_set_id=task_set_id,
        kind="matrix",
        content={"schema_version": "1.0.0-dev"},
        schema_version="1.0.0-dev",
        valid=True,
        status="draft",
    )


def _fake_gateway(payload: dict):
    """构造 mock gateway 工厂：run_stage 返回带 payload 的伪 invocation。"""

    class _Inv:
        id = 1
        status = "success"
        parsed_json = payload
        duration_ms = 12
        mock = True
        error = ""
        workspace_path = ""

    class _GW:
        def run_stage(self, *a, **kw):
            return _Inv()

    return _GW()


class ReviewStageTests(TestCase):
    def _ts(self):
        ts = create_task_set("评审测试", recording_id=1)
        ts.status = "design_done"
        ts.save(update_fields=["status", "updated_at"])
        _make_drafts(ts.id)
        return ts

    def test_verdict_pass(self):
        from unittest.mock import patch

        from .stages import run_review_stage

        ts = self._ts()
        with patch("apps.tasksets.stages.get_gateway",
                   return_value=_fake_gateway({"verdict": "pass", "blocking_issues": [],
                                               "suggestions": ["x"], "confidence": 0.9})):
            ts = run_review_stage(ts)
        self.assertEqual(ts.status, "review_done")
        job = StageJob.objects.get(task_set=ts, stage="review")
        self.assertEqual(job.status, "success")
        self.assertEqual(job.detail.get("verdict"), "pass")

    def test_verdict_changes_needed(self):
        from unittest.mock import patch

        from .stages import run_review_stage

        ts = self._ts()
        with patch("apps.tasksets.stages.get_gateway",
                   return_value=_fake_gateway({"verdict": "changes_needed",
                                               "blocking_issues": ["缺空密码用例"],
                                               "suggestions": [], "confidence": 0.6})), \
             patch.dict("os.environ", {"DSHOPS_REVIEW_AUTO_PASS": ""}, clear=False):
            ts = run_review_stage(ts)
        self.assertEqual(ts.status, "failed")
        self.assertIn("缺空密码用例", ts.error)

    def test_verdict_changes_needed_auto_pass(self):
        """DSHOPS_REVIEW_AUTO_PASS=1 时 changes_needed 放行（问题留档）。"""
        from unittest.mock import patch

        from .stages import run_review_stage

        ts = self._ts()
        with patch("apps.tasksets.stages.get_gateway",
                   return_value=_fake_gateway({"verdict": "changes_needed",
                                               "blocking_issues": ["缺空密码用例"],
                                               "suggestions": [], "confidence": 0.6})), \
             patch.dict("os.environ", {"DSHOPS_REVIEW_AUTO_PASS": "1"}, clear=False):
            ts = run_review_stage(ts)
        self.assertEqual(ts.status, "review_done")
        job = StageJob.objects.get(task_set=ts, stage="review")
        self.assertTrue(job.detail.get("auto_pass"))

    def test_guard(self):
        from .stages import run_review_stage

        ts = create_task_set("守卫测试", recording_id=1)  # status=created
        with self.assertRaises(ValueError):
            run_review_stage(ts)


class GenerateStageTests(TestCase):
    def _ts(self):
        ts = create_task_set("生成测试", recording_id=1)
        ts.status = "review_done"
        ts.save(update_fields=["status", "updated_at"])
        _make_drafts(ts.id)
        return ts

    def test_generate_pass(self):
        from unittest.mock import patch

        from .models import GeneratedRun
        from .stages import run_generate_stage

        ts = self._ts()
        payload = {
            "status": "pass", "script_file": "test_login.py",
            "rounds": 2, "summary": "修了断言时机",
            "script_content": "print('x')", "output_tail": "1 passed",
        }
        with patch("apps.tasksets.stages.get_gateway",
                   return_value=_fake_gateway(payload)):
            ts = run_generate_stage(ts)
        self.assertEqual(ts.status, "generate_done")
        gr = GeneratedRun.objects.get(task_set_id=ts.id)
        self.assertEqual(gr.status, "pass")
        self.assertEqual(gr.script_file, "test_login.py")
        self.assertEqual(gr.script_content, "print('x')")
        self.assertEqual(gr.rounds, 2)

    def test_generate_fail(self):
        from unittest.mock import patch

        from .models import GeneratedRun
        from .stages import run_generate_stage

        ts = self._ts()
        payload = {"status": "fail", "script_file": "test_login.py", "rounds": 3,
                   "summary": "定位器不稳定", "script_content": "", "output_tail": "1 failed"}
        with patch("apps.tasksets.stages.get_gateway",
                   return_value=_fake_gateway(payload)):
            ts = run_generate_stage(ts)
        self.assertEqual(ts.status, "failed")
        gr = GeneratedRun.objects.get(task_set_id=ts.id)
        self.assertEqual(gr.status, "fail")

    def test_generate_guard(self):
        from .stages import run_generate_stage

        ts = create_task_set("守卫测试", recording_id=1)
        with self.assertRaises(ValueError):
            run_generate_stage(ts)


class PipelineTests(TestCase):
    def test_pipeline_full_chain_mock(self):
        from unittest.mock import patch

        from apps.recorder.models import Recording

        demo_script = (
            'from playwright.sync_api import sync_playwright\n\n\n'
            'def run(playwright):\n'
            '    browser = playwright.chromium.launch(headless=False)\n'
            '    page = browser.new_page()\n'
            '    page.goto("http://127.0.0.1:8001/api/demo/login/")\n'
            '    page.get_by_role("textbox", name="请输入用户名").click()\n'
            '    page.get_by_role("textbox", name="请输入用户名").fill("testadmin")\n'
            '    page.get_by_role("textbox", name="请输入密码").fill("admin123456")\n'
            '    page.get_by_role("button", name="登录", exact=True).click()\n'
            '    page.get_by_text("欢迎回来").click()\n'
            '    browser.close()\n\n\n'
            'with sync_playwright() as playwright:\n'
            '    run(playwright)\n'
        )
        rec = Recording.objects.create(
            name="pipeline-录制", raw_content=demo_script
        )
        ts = create_task_set("流水线测试", recording_id=rec.id)
        ts.status = "replay_done"  # 跳过真实回放（同步建任务的回放由外部负责）
        ts.save(update_fields=["status", "updated_at"])

        # 让 extract/design/review/generate 全部走 mock
        gateway_payloads = [
            {"schema_version": "1.0.0-dev", "source": {"recording_id": "1", "trace_artifact_id": "t"},
             "pages": [{"id": "p0", "name": "登录页", "url_pattern": "http://127.0.0.1:8001/api/demo/login/"}],
             "elements": [{"id": "e0", "page_id": "p0", "name": "登录", "role": "button",
                           "candidates": [{"type": "role", "value": "button", "priority": 0, "robustness": "strong"}],
                           "exists_in_repo": False}],
             "actions": [], "params": [], "confidence": 0.9},
            {"schema_version": "1.0.0-dev", "pom_ref": "p1", "module": "登录",
             "rows": [{"id": "r0", "name": "正常登录", "method_tags": ["scenario"],
                       "classification": "separate_flow", "flow": [0], "params": {}}]},
            {"verdict": "pass", "blocking_issues": [], "suggestions": [], "confidence": 0.9},
            {"status": "pass", "script_file": "test_login.py", "rounds": 1,
             "summary": "ok", "script_content": "print('ok')", "output_tail": "1 passed"},
        ]
        with patch("apps.tasksets.stages.get_gateway") as mock_gw:
            # 直接让 gateway 走真实 mock fixtures（复用 AgentGateway mock 模式）
            from apps.agent_runtime.gateway import AgentGateway

            gw = AgentGateway()
            gw.mode = "mock"
            mock_gw.return_value = gw

            from .stages import run_pipeline

            ts = run_pipeline(ts)

        self.assertEqual(ts.status, "generate_done")
        stages = list(StageJob.objects.filter(task_set=ts).order_by("id").values_list("stage", flat=True))
        self.assertEqual(stages, ["extract", "design", "review", "generate"])
        for s in ["extract", "design", "review", "generate"]:
            job = StageJob.objects.get(task_set=ts, stage=s)
            self.assertEqual(job.status, "success", f"{s} 应成功")

    def test_pipeline_stops_on_review_fail(self):
        from unittest.mock import patch

        from apps.agent_runtime.gateway import AgentGateway
        from .stages import run_pipeline

        ts = create_task_set("流水线失败测试", recording_id=1)
        ts.status = "replay_done"
        ts.save(update_fields=["status", "updated_at"])

        gw = AgentGateway()
        gw.mode = "mock"
        with patch("apps.tasksets.stages.get_gateway", return_value=gw):
            # 把 mock review fixture 换成 verdict=changes_needed
            import json
            from pathlib import Path

            fixture = Path("apps/agent_runtime/fixtures/mock_review.json")
            orig = json.loads(fixture.read_text(encoding="utf-8"))
            fixture.write_text(
                json.dumps({**orig, "verdict": "changes_needed",
                            "blocking_issues": ["覆盖不足"]}, ensure_ascii=False),
                encoding="utf-8",
            )
            try:
                ts = run_pipeline(ts)
            finally:
                fixture.write_text(json.dumps(orig, ensure_ascii=False), encoding="utf-8")

        self.assertEqual(ts.status, "failed")
        self.assertNotIn("generate", list(
            StageJob.objects.filter(task_set=ts).values_list("stage", flat=True)))


class ObsCenterApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_overview(self):
        resp = self.client.get("/api/obs/overview/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        for key in ("invocations", "replays", "stages", "generated"):
            self.assertIn(key, data)

    def test_activity(self):
        resp = self.client.get("/api/obs/activity/?limit=10")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.json())
