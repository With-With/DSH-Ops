"""P4 #2 修复验证：codegen 落库解析 + 回放列表按 recording_id 过滤。"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from apps.recorder.models import Recording

from .codegen import stop_session
from .codegen import _sessions, _sessions_lock

from apps.replay.models import ReplayRun


DEMO_SCRIPT = (
    'from playwright.sync_api import sync_playwright\n\n\n'
    'def run(playwright):\n'
    '    browser = playwright.chromium.launch(headless=False)\n'
    '    page = browser.new_page()\n'
    '    page.goto("http://127.0.0.1:8000/api/demo/login/")\n'
    '    page.get_by_role("textbox", name="请输入用户名").click()\n'
    '    page.get_by_role("textbox", name="请输入用户名").fill("testadmin")\n'
    '    page.get_by_role("button", name="登录", exact=True).click()\n'
    '    browser.close()\n\n\n'
    'with sync_playwright() as playwright:\n'
    '    run(playwright)\n'
)


class CodegenParseOnSaveTests(TestCase):
    @patch("apps.recorder.codegen.subprocess.Popen")
    def test_stop_session_parses_fields(self, mock_popen):
        # 模拟 start 后的会话 + 产物文件
        import tempfile
        from pathlib import Path

        tmp = Path(tempfile.mkdtemp()) / "raw_script.py"
        tmp.write_text(DEMO_SCRIPT, encoding="utf-8")

        with _sessions_lock:
            _sessions.clear()
            _sessions["s1"] = {
                "session_id": "s1", "name": "codegen-demo",
                "start_url": "http://127.0.0.1:8000/api/demo/login/",
                "started_at": "2026-01-01T00:00:00",
                "pid": 1, "output_file": str(tmp), "stopped": False,
            }
        try:
            result = stop_session("s1")
            self.assertTrue(result["ok"])
            rec = Recording.objects.get(pk=result["recording_id"])
            self.assertGreater(rec.actions_count, 0, "动作数应为解析结果")
            self.assertGreater(rec.locators_count, 0, "定位器数应为解析结果")
            self.assertEqual(
                rec.start_url, "http://127.0.0.1:8000/api/demo/login/"
            )
            self.assertEqual(rec.language, "python")
        finally:
            with _sessions_lock:
                _sessions.clear()


class ReplayFilterTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.rec1 = Recording.objects.create(name="r1", raw_content="x")
        self.rec2 = Recording.objects.create(name="r2", raw_content="y")
        self.run1 = ReplayRun.objects.create(recording=self.rec1, status="success")
        self.run2 = ReplayRun.objects.create(recording=self.rec2, status="success")

    def test_list_filters_by_recording_id(self):
        resp = self.client.get(f"/api/replays/?recording_id={self.rec1.id}")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        ids = [r["id"] for r in results]
        self.assertEqual(ids, [self.run1.id])
        self.assertNotIn(self.run2.id, ids)

    def test_list_filters_by_status(self):
        self.run1.status = "failed"
        self.run1.save(update_fields=["status", "updated_at"])
        resp = self.client.get("/api/replays/?status=success")
        ids = [r["id"] for r in resp.json()["results"]]
        self.assertEqual(ids, [self.run2.id])
