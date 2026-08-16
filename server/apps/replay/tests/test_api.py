"""replay API 与 demo 视图单元测试。"""
import os

from django.test import TestCase
from rest_framework.test import APIClient

from apps.recorder.models import Recording
from apps.replay.models import ReplayRun


GOLD_SAMPLE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "scripts", "demo_login_recorded.py",
)


class DemoLoginViewTest(TestCase):
    def test_demo_login_page(self):
        response = self.client.get("/api/demo/login/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("DSH-Ops 演示登录", response.content.decode("utf-8"))
        self.assertIn("请输入用户名", response.content.decode("utf-8"))
        self.assertIn("请输入密码", response.content.decode("utf-8"))
        self.assertIn("登录", response.content.decode("utf-8"))
        self.assertIn("欢迎回来", response.content.decode("utf-8"))


class ReplayRunAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        with open(GOLD_SAMPLE_PATH, "r", encoding="utf-8") as f:
            self.sample_content = f.read()

    def _create_recording(self):
        return Recording.objects.create(
            name="test",
            language="python",
            framework="playwright",
            start_url="http://example.com",
            raw_content=self.sample_content,
            normalized_content=self.sample_content,
            locators_count=5,
            actions_count=6,
        )

    def test_list_replays(self):
        rec = self._create_recording()
        ReplayRun.objects.create(
            recording=rec,
            status="success",
            duration_ms=1000,
            steps_total=5,
            steps_passed=5,
        )
        response = self.client.get("/api/replays/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        results = data.get("results", data)
        self.assertEqual(len(results), 1)

    def test_retrieve_replay(self):
        rec = self._create_recording()
        run = ReplayRun.objects.create(
            recording=rec,
            status="failed",
            duration_ms=500,
            steps_total=5,
            steps_passed=2,
            error="step 2 failed",
        )
        response = self.client.get(f"/api/replays/{run.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "failed")
        self.assertEqual(data["steps_passed"], 2)
        self.assertEqual(data["recording_name"], "test")
        self.assertIn("trace_available", data)

    def test_create_replay_missing_recording(self):
        response = self.client.post(
            "/api/replays/",
            {"recording_id": 99999},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_trace_download_not_found(self):
        rec = self._create_recording()
        run = ReplayRun.objects.create(
            recording=rec,
            status="success",
            trace_path="",
        )
        response = self.client.get(f"/api/replays/{run.pk}/trace/download/")
        self.assertEqual(response.status_code, 404)
