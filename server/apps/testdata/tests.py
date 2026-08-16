"""
testdata 单元测试：
- ParameterSet CRUD
- secret 值序列化脱敏
- POST 明文入库
- 软删不可见
"""
from django.test import TestCase
from rest_framework.test import APIClient

from .models import ParameterSet
from .serializers import _mask_secret_values


class MaskSecretValuesTests(TestCase):
    def test_no_secret_keys(self):
        values = {"username": "alice", "password": "secret123"}
        self.assertEqual(_mask_secret_values(values, []), values)

    def test_mask_single(self):
        values = {"username": "alice", "password": "secret123"}
        masked = _mask_secret_values(values, ["password"])
        self.assertEqual(masked["username"], "alice")
        self.assertEqual(masked["password"], "${secret:password}")

    def test_mask_multiple(self):
        values = {"a": "1", "b": "2", "c": "3"}
        masked = _mask_secret_values(values, ["a", "c"])
        self.assertEqual(masked["a"], "${secret:a}")
        self.assertEqual(masked["b"], "2")
        self.assertEqual(masked["c"], "${secret:c}")

    def test_key_not_in_values(self):
        """secret_keys 里有 values 中不存在的键，不报错。"""
        values = {"username": "alice"}
        masked = _mask_secret_values(values, ["password"])
        self.assertEqual(masked["username"], "alice")
        self.assertNotIn("password", masked)

    def test_empty_values(self):
        self.assertEqual(_mask_secret_values({}, ["a"]), {})


class ParameterSetModelTests(TestCase):
    def test_create(self):
        ps = ParameterSet.objects.create(
            name="登录凭据",
            values={"username": "admin", "password": "P@ssw0rd"},
            secret_keys=["password"],
        )
        self.assertEqual(ps.values["password"], "P@ssw0rd")  # 明文存


class ParameterSetApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ps = ParameterSet.objects.create(
            name="API 测试凭据",
            values={"api_key": "sk-12345", "endpoint": "https://api.example.com"},
            secret_keys=["api_key"],
        )

    def test_list_params_masked(self):
        resp = self.client.get("/api/testdata/params/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["count"], 1)
        values = data["results"][0]["values"]
        # secret 被脱敏
        self.assertEqual(values["api_key"], "${secret:api_key}")
        # 非 secret 明文
        self.assertEqual(values["endpoint"], "https://api.example.com")

    def test_retrieve_masked(self):
        resp = self.client.get(f"/api/testdata/params/{self.ps.id}/")
        self.assertEqual(resp.status_code, 200)
        values = resp.json()["values"]
        self.assertEqual(values["api_key"], "${secret:api_key}")

    def test_create_with_plaintext(self):
        """POST 允许明文。"""
        resp = self.client.post(
            "/api/testdata/params/",
            {
                "name": "新凭据",
                "values": {"token": "tok-secret", "env": "prod"},
                "secret_keys": ["token"],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        # 数据库里是明文
        ps = ParameterSet.objects.get(name="新凭据")
        self.assertEqual(ps.values["token"], "tok-secret")
        # 返回值中是脱敏的
        self.assertEqual(resp.json()["values"]["token"], "${secret:token}")

    def test_name_unique(self):
        """name 唯一约束。"""
        resp = self.client.post(
            "/api/testdata/params/",
            {
                "name": "API 测试凭据",  # 与 setUp 同名
                "values": {},
                "secret_keys": [],
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_delete_soft(self):
        resp = self.client.delete(f"/api/testdata/params/{self.ps.id}/")
        self.assertEqual(resp.status_code, 204)
        # 列表中不可见
        resp = self.client.get("/api/testdata/params/")
        self.assertEqual(resp.json()["count"], 0)
        # 数据库里还在
        self.assertTrue(ParameterSet.all_objects.filter(id=self.ps.id).exists())

    def test_secret_keys_validation_list(self):
        resp = self.client.post(
            "/api/testdata/params/",
            {"name": "bad1", "values": {}, "secret_keys": "not-a-list"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_values_validation_dict(self):
        resp = self.client.post(
            "/api/testdata/params/",
            {"name": "bad2", "values": [1, 2, 3], "secret_keys": []},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
