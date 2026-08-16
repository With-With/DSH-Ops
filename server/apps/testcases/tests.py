"""testcases（用例管理）单测。

注意：本 app 模型名为 TestCase，与 django.test.TestCase 同名——
模型导入必须用别名，否则测试基类被模型类覆盖（经典坑）。
"""
from django.test import TestCase as DjangoTestCase
from rest_framework.test import APIClient

from .models import TestCase as TestCaseModel


class TestCaseApiTests(DjangoTestCase):
    def setUp(self):
        self.client = APIClient()
        self.tc = TestCaseModel.objects.create(
            name="登录用例", recording_id=1,
            content="class BasePage:\n    pass\n\ndef test_login():\n    pass",
            source="ai_normalized", status="ready",
        )

    def test_list(self):
        resp = self.client.get("/api/testcases/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["count"], 1)

    def test_create(self):
        resp = self.client.post(
            "/api/testcases/",
            {"name": "新建", "content": "print(1)", "source": "manual"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(TestCaseModel.objects.count(), 2)

    def test_detail_content(self):
        resp = self.client.get(f"/api/testcases/{self.tc.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("class BasePage", resp.json()["content"])

    def test_soft_delete(self):
        self.client.delete(f"/api/testcases/{self.tc.id}/")
        self.assertEqual(TestCaseModel.objects.count(), 0)
        self.assertEqual(TestCaseModel.all_objects.count(), 1)

    def test_bulk_delete(self):
        t2 = TestCaseModel.objects.create(name="b", content="x")
        resp = self.client.post(
            "/api/testcases/bulk-delete/", {"ids": [self.tc.id, t2.id]}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted"], 2)
        self.assertEqual(TestCaseModel.objects.count(), 0)

    def test_bulk_delete_empty_400(self):
        resp = self.client.post("/api/testcases/bulk-delete/", {"ids": []}, format="json")
        self.assertEqual(resp.status_code, 400)
