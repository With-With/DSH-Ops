"""Recorder API 单元测试。"""
import os

from django.test import TestCase
from rest_framework.test import APIClient

from apps.recorder.models import Recording


GOLD_SAMPLE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..", "..", "scripts", "demo_login_recorded.py",
)


class RecordingAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
        with open(GOLD_SAMPLE_PATH, "r", encoding="utf-8") as f:
            self.sample_content = f.read()

    def test_create_recording(self):
        response = self.client.post(
            "/api/recordings/",
            {
                "name": "test recording",
                "content": self.sample_content,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["name"], "test recording")
        self.assertEqual(data["language"], "python")
        self.assertEqual(data["framework"], "playwright")
        self.assertIn("actions", data)
        self.assertGreater(data["actions_count"], 0)
        self.assertIsInstance(data["warnings"], list)

    def test_create_empty_content_fails(self):
        response = self.client.post(
            "/api/recordings/",
            {"name": "empty", "content": ""},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_list_recordings(self):
        Recording.objects.create(
            name="r1",
            raw_content='page.goto("http://a.com")',
            normalized_content='page.goto("http://a.com")',
        )
        Recording.objects.create(
            name="r2",
            raw_content='page.goto("http://b.com")',
            normalized_content='page.goto("http://b.com")',
        )
        response = self.client.get("/api/recordings/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # DRF 分页包装
        if "results" in data:
            results = data["results"]
        else:
            results = data
        self.assertEqual(len(results), 2)

    def test_retrieve_recording(self):
        rec = Recording.objects.create(
            name="detail-test",
            raw_content=self.sample_content,
            normalized_content=self.sample_content,
        )
        response = self.client.get(f"/api/recordings/{rec.pk}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "detail-test")
        self.assertIn("actions", data)
        self.assertIsInstance(data["actions"], list)
        self.assertGreater(len(data["actions"]), 0)

    def test_soft_delete(self):
        rec = Recording.objects.create(
            name="del-test",
            raw_content='page.goto("http://x.com")',
            normalized_content='page.goto("http://x.com")',
        )
        pk = rec.pk
        response = self.client.delete(f"/api/recordings/{pk}/")
        self.assertEqual(response.status_code, 200)

        # 软删后默认查询看不到
        self.assertFalse(Recording.objects.filter(pk=pk).exists())
        # 全量查询能看到
        self.assertTrue(Recording.all_objects.filter(pk=pk).exists())
        rec_deleted = Recording.all_objects.get(pk=pk)
        self.assertTrue(rec_deleted.is_deleted)

    def test_actions_endpoint(self):
        rec = Recording.objects.create(
            name="act-test",
            raw_content='page.goto("http://x.com")\npage.get_by_role("button").click()',
            normalized_content="",
        )
        response = self.client.get(f"/api/recordings/{rec.pk}/actions/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("actions", data)
        self.assertEqual(len(data["actions"]), 2)
