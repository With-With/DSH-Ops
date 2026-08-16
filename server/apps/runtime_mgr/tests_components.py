"""P4 #1：组件检测/安装/删除 单测。"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .components import detect_components


class ComponentDetectTests(TestCase):
    @patch("apps.runtime_mgr.components._has_module")
    @patch("apps.runtime_mgr.components._playwright_browser_available")
    @patch("apps.runtime_mgr.components._detect_browser")
    def test_detect_structure(self, mock_browser, mock_pw_avail, mock_module):
        mock_module.side_effect = lambda m: m == "playwright"
        mock_pw_avail.return_value = True
        mock_browser.return_value = {"installed": True, "path": "C:/x/msedge.exe"}

        items = detect_components()
        keys = [i["key"] for i in items]
        self.assertIn("playwright", keys)
        self.assertIn("selenium", keys)
        self.assertIn("browser-msedge", keys)
        self.assertIn("browser-chrome", keys)
        self.assertIn("pw-chromium", keys)

        pw = next(i for i in items if i["key"] == "playwright")
        self.assertTrue(pw["installed"])
        self.assertIn("install", pw["actions"])
        self.assertIn("delete", pw["actions"])

        se = next(i for i in items if i["key"] == "selenium")
        self.assertFalse(se["installed"])
        self.assertNotIn("delete", se["actions"])

        edge = next(i for i in items if i["key"] == "browser-msedge")
        self.assertTrue(edge["installed"])

    def test_detect_real(self):
        """真实环境冒烟：不 mock，只验证结构与字段类型。"""
        items = detect_components()
        self.assertGreaterEqual(len(items), 5)
        for item in items:
            self.assertIn("key", item)
            self.assertIn("installed", item)
            self.assertIsInstance(item["installed"], bool)


class ComponentApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_install_requires_key(self):
        resp = self.client.post("/api/runtimes/components/install/", {}, format="json")
        self.assertEqual(resp.status_code, 400)

    @patch("apps.runtime_mgr.components.is_task_running", return_value=True)
    def test_install_conflict_409(self, mock_running):
        resp = self.client.post(
            "/api/runtimes/components/install/", {"key": "playwright"}, format="json"
        )
        self.assertEqual(resp.status_code, 409)

    @patch("apps.runtime_mgr.components.install_component", side_effect=ValueError("不支持"))
    def test_install_unsupported_400(self, mock_install):
        resp = self.client.post(
            "/api/runtimes/components/install/", {"key": "bogus"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    def test_delete_requires_confirm(self):
        resp = self.client.post(
            "/api/runtimes/components/delete/", {"key": "playwright"}, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    @patch("apps.runtime_mgr.components.is_task_running", return_value=False)
    @patch("apps.runtime_mgr.components.delete_component", return_value="pip uninstall x")
    def test_delete_ok(self, mock_delete, mock_running):
        resp = self.client.post(
            "/api/runtimes/components/delete/",
            {"key": "playwright", "confirm": True},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "running")

    def test_components_list(self):
        resp = self.client.get("/api/runtimes/components/")
        self.assertEqual(resp.status_code, 200)
        results = resp.json()["results"]
        self.assertGreaterEqual(len(results), 5)
        for item in results:
            self.assertIn("op_status", item)
