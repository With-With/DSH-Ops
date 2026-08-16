"""P4：元素批量删除 端点测试。"""
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Element, PageObject


class ElementBulkDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.page = PageObject.objects.create(name="p", url_pattern="/")
        self.e1 = Element.objects.create(page=self.page, name="a", role="button", candidates=[])
        self.e2 = Element.objects.create(page=self.page, name="b", role="textbox", candidates=[])
        self.e3 = Element.objects.create(page=self.page, name="c", role="link", candidates=[])

    def test_bulk_delete(self):
        resp = self.client.post(
            "/api/assets/elements/bulk-delete/",
            {"ids": [self.e1.id, self.e2.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted"], 2)
        self.assertEqual(Element.objects.count(), 1)
        self.assertEqual(Element.all_objects.count(), 3)

    def test_bulk_delete_empty_400(self):
        resp = self.client.post("/api/assets/elements/bulk-delete/", {"ids": []}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_bulk_delete_nonexistent(self):
        resp = self.client.post(
            "/api/assets/elements/bulk-delete/", {"ids": [99999]}, format="json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted"], 0)
