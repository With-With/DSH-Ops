"""replay.runner 单元测试（mock playwright，不启浏览器）。"""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch


class TestRunReplayMock(unittest.TestCase):
    """用 mock 验证 run_replay 的成功路径、失败路径与 trace_hash 写入。"""

    def setUp(self):
        # 确保能 import Django 模型（测试环境已设置 DJANGO_SETTINGS_MODULE）
        import django
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        try:
            django.setup()
        except Exception:
            pass

    def _make_recording(self):
        from apps.recorder.models import Recording
        content = (
            'page.goto("http://example.com")\n'
            'page.get_by_role("button", name="登录").click()\n'
        )
        return Recording.objects.create(
            name="mock-test",
            language="python",
            framework="playwright",
            start_url="http://example.com",
            raw_content=content,
            normalized_content=content,
            locators_count=1,
            actions_count=2,
        )

    def test_success_path(self):
        """成功路径：trace 文件生成，status=success，hash 写入，steps_passed=总数。"""
        from apps.replay.runner import run_replay

        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建一个假的 trace.zip 文件（用来验证 hash 计算）
            trace_dir = os.path.join(tmpdir, "test_trace")
            os.makedirs(trace_dir, exist_ok=True)
            fake_trace = os.path.join(trace_dir, "trace.zip")
            with open(fake_trace, "wb") as f:
                f.write(b"fake trace content for hash test" * 10)

            mock_browser = MagicMock()
            mock_context = MagicMock()
            mock_page = MagicMock()
            mock_locator = MagicMock()

            # 使得 context.new_page() 返回 mock_page
            mock_context.new_page.return_value = mock_page
            # page.goto / page.get_by_role 返回 locator
            mock_page.goto = MagicMock()
            mock_page.get_by_role = MagicMock(return_value=mock_locator)
            mock_page.get_by_text = MagicMock(return_value=mock_locator)
            mock_page.locator = MagicMock(return_value=mock_locator)
            # locator.click / fill / press
            mock_locator.click = MagicMock()
            mock_locator.fill = MagicMock()
            mock_locator.press = MagicMock()

            # tracing.start / stop —— stop 时写文件
            def tracing_stop_side_effect(path=None):
                # 把 fake trace 复制到目标路径
                if path:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    import shutil
                    shutil.copy(fake_trace, path)
            mock_context.tracing.stop.side_effect = tracing_stop_side_effect

            mock_browser.new_context.return_value = mock_context

            mock_pw = MagicMock()
            mock_pw.chromium.launch.return_value = mock_browser

            # sync_playwright 在函数内 import，所以 patch playwright.sync_api
            with patch("playwright.sync_api.sync_playwright") as mock_sp:
                mock_sp.return_value.__enter__.return_value = mock_pw

                recording = self._make_recording()
                run = run_replay(recording, artifacts_dir=tmpdir)

                self.assertEqual(run.status, "success")
                self.assertEqual(run.steps_total, 2)
                self.assertEqual(run.steps_passed, 2)
                self.assertTrue(run.trace_path)
                self.assertTrue(os.path.exists(run.trace_path))
                self.assertTrue(os.path.getsize(run.trace_path) > 0)
                self.assertTrue(run.trace_hash)
                self.assertEqual(len(run.trace_hash), 32)
                self.assertEqual(run.error, "")

    def test_failure_path(self):
        """失败路径：第二步抛异常，status=failed，error 含步骤 index。"""
        from apps.replay.runner import run_replay

        with tempfile.TemporaryDirectory() as tmpdir:
            trace_dir = os.path.join(tmpdir, "test_trace_fail")
            os.makedirs(trace_dir, exist_ok=True)
            fake_trace = os.path.join(trace_dir, "trace.zip")
            with open(fake_trace, "wb") as f:
                f.write(b"partial trace" * 5)

            mock_browser = MagicMock()
            mock_context = MagicMock()
            mock_page = MagicMock()
            mock_locator = MagicMock()

            mock_context.new_page.return_value = mock_page
            mock_page.goto = MagicMock()
            mock_page.get_by_role = MagicMock(return_value=mock_locator)
            mock_locator.click = MagicMock(side_effect=RuntimeError("element not found"))

            def tracing_stop_side_effect(path=None):
                if path:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    import shutil
                    shutil.copy(fake_trace, path)
            mock_context.tracing.stop.side_effect = tracing_stop_side_effect

            mock_browser.new_context.return_value = mock_context

            mock_pw = MagicMock()
            mock_pw.chromium.launch.return_value = mock_browser

            with patch("playwright.sync_api.sync_playwright") as mock_sp:
                mock_sp.return_value.__enter__.return_value = mock_pw

                recording = self._make_recording()
                run = run_replay(recording, artifacts_dir=tmpdir)

                self.assertEqual(run.status, "failed")
                self.assertEqual(run.steps_passed, 1)  # goto 通过，click 失败
                self.assertIn("步骤 1", run.error)
                self.assertIn("RuntimeError", run.error)
                # 即使失败也应该有 trace（如果已生成）
                self.assertTrue(run.trace_hash or run.trace_path == "")

    def test_trace_hash_consistency(self):
        """验证 trace_hash 是 sha256 前 32 位。"""
        from apps.replay.runner import _sha256_hex

        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as f:
            f.write(b"test content for hash")
            path = f.name

        try:
            h = _sha256_hex(path)
            self.assertEqual(len(h), 32)
            # 同内容同 hash
            self.assertEqual(h, _sha256_hex(path))
            # 应该是十六进制
            int(h, 16)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
