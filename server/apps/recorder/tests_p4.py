"""P4 #3：codegen 会话 + AI 重组 单测（不真起浏览器）。"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.recorder.models import Recording

from .codegen import get_status, normalize_is_running
from .normalizer import SCAFFOLD_TEMPLATE, normalize_recording


DEMO_SCRIPT = (
    'from playwright.sync_api import sync_playwright\n\n\n'
    'def run(playwright):\n'
    '    browser = playwright.chromium.launch(headless=False)\n'
    '    page = browser.new_page()\n'
    '    page.goto("http://127.0.0.1:8001/api/demo/login/")\n'
    '    page.get_by_role("textbox", name="请输入用户名").click()\n'
    '    page.get_by_role("textbox", name="请输入用户名").fill("testadmin")\n'
    '    page.get_by_role("button", name="登录", exact=True).click()\n'
    '    browser.close()\n\n\n'
    'with sync_playwright() as playwright:\n'
    '    run(playwright)\n'
)


class CodegenApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch("apps.recorder.codegen.get_status", return_value={"active": True})
    def test_start_conflict_409(self, mock_status):
        resp = self.client.post("/api/recordings/codegen/start/", {}, format="json")
        self.assertEqual(resp.status_code, 409)

    @patch("apps.recorder.codegen.get_status", return_value={"active": False})
    @patch("apps.recorder.codegen.start_session")
    def test_start_202(self, mock_start, mock_status):
        mock_start.return_value = {
            "session_id": "abc123", "name": "n", "start_url": "http://x/",
            "started_at": "2026-01-01T00:00:00",
        }
        resp = self.client.post("/api/recordings/codegen/start/", {}, format="json")
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.json()["session_id"], "abc123")

    def test_stop_requires_session_id(self):
        resp = self.client.post("/api/recordings/codegen/stop/", {}, format="json")
        self.assertEqual(resp.status_code, 400)

    @patch("apps.recorder.codegen.stop_session")
    def test_stop_ok(self, mock_stop):
        mock_stop.return_value = {"ok": True, "recording_id": 7, "actions_count": 4}
        resp = self.client.post(
            "/api/recordings/codegen/stop/", {"session_id": "s1", "auto_analyze": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        mock_stop.assert_called_once_with("s1", auto_analyze=True)

    def test_status_endpoint(self):
        resp = self.client.get("/api/recordings/codegen/status/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("active", resp.json())


class NormalizerTests(TestCase):
    def setUp(self):
        self.rec = Recording.objects.create(name="t", raw_content=DEMO_SCRIPT)

    @patch.dict("os.environ", {"DSHOPS_AGENT_MODE": "mock"}, clear=False)
    def test_mock_normalize_produces_scaffold(self):
        normalize_recording(self.rec)
        self.rec.refresh_from_db()
        content = self.rec.normalized_content
        self.assertIn("pytest", content)
        self.assertIn("browser_page", content)
        self.assertIn("channel=", content)
        self.assertIn("test_main_flow", content)
        self.assertIn("page.goto", content)
        self.assertFalse(normalize_is_running(self.rec.id))

    @patch.dict("os.environ", {"DSHOPS_AGENT_MODE": "mock"}, clear=False)
    def test_mock_normalize_idempotent(self):
        normalize_recording(self.rec)
        first = Recording.objects.get(pk=self.rec.pk).normalized_content
        normalize_recording(self.rec)
        second = Recording.objects.get(pk=self.rec.pk).normalized_content
        self.assertEqual(first, second)

    @patch.dict("os.environ", {"DSHOPS_AGENT_MODE": "real"}, clear=False)
    @patch("apps.agent_runtime.gateway.AgentGateway")
    def test_real_normalize_strips_fence(self, mock_gw):
        class _Inv:
            status = "success"
            output_text = "前言\n```python\nimport pytest\nprint('ok')\n```\n尾"
            error = ""
            parsed_json = None

        mock_gw.return_value.run_stage.return_value = _Inv()
        normalize_recording(self.rec)
        self.rec.refresh_from_db()
        self.assertIn("import pytest", self.rec.normalized_content)
        self.assertNotIn("```", self.rec.normalized_content)

    @patch.dict("os.environ", {"DSHOPS_AGENT_MODE": "real"}, clear=False)
    @patch("apps.agent_runtime.gateway.AgentGateway")
    def test_real_failure_appends_warning(self, mock_gw):
        class _Inv:
            status = "failed"
            output_text = ""
            error = "boom"
            parsed_json = None

        mock_gw.return_value.run_stage.return_value = _Inv()
        normalize_recording(self.rec)
        self.rec.refresh_from_db()
        self.assertEqual(self.rec.normalized_content, "")
        self.assertTrue(any("boom" in w for w in self.rec.warnings))

    @patch.dict("os.environ", {"DSHOPS_AGENT_MODE": "mock"}, clear=False)
    def test_normalize_api_202_and_status(self):
        resp = self.client.post(f"/api/recordings/{self.rec.id}/normalize/", format="json")
        self.assertEqual(resp.status_code, 202)
        # 线程启动即返回；running 标志最终应清除（线程写库在 TestCase 事务外，
        # 主线程读不到其提交，故"done"由下一用例同步验证）
        import time
        for _ in range(20):
            if not normalize_is_running(self.rec.id):
                break
            time.sleep(0.1)
        self.assertFalse(normalize_is_running(self.rec.id))

    @patch.dict("os.environ", {"DSHOPS_AGENT_MODE": "mock"}, clear=False)
    def test_normalize_status_done_sync(self):
        normalize_recording(self.rec)  # 主线程同步执行，写入可见
        detail = self.client.get(f"/api/recordings/{self.rec.id}/").json()
        self.assertEqual(detail["normalize_status"], "done")
        self.assertIn("test_main_flow", detail["normalized_content"])

    def test_scaffold_contains_required_marks(self):
        self.assertIn("# STEP:", SCAFFOLD_TEMPLATE)
        self.assertIn('channel="chromium"', SCAFFOLD_TEMPLATE)
