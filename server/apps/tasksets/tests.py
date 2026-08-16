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

    def test_failed_is_terminal(self):
        """failed 是终态，不能转去任何状态。"""
        self.assertEqual(len(allowed_transitions["failed"]), 0)
        for target in ["created", "replaying", "replay_done"]:
            with self.assertRaises(ValueError):
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
