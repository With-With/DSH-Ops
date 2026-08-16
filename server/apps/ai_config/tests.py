"""ai_config 单测：加密/掩码、CRUD 契约、默认互斥、连通测试 mock。"""
from unittest.mock import patch

from django.test import TestCase
from rest_framework.test import APIClient

from .crypto import decrypt_key, encrypt_key, mask_key
from .models import AIProviderConfig


class CryptoTests(TestCase):
    def test_roundtrip(self):
        enc = encrypt_key("sk-test-12345678")
        self.assertNotEqual(enc, "sk-test-12345678")
        self.assertEqual(decrypt_key(enc), "sk-test-12345678")

    def test_empty(self):
        self.assertEqual(encrypt_key(""), "")
        self.assertEqual(decrypt_key(""), "")

    def test_invalid_cipher(self):
        self.assertEqual(decrypt_key("not-a-valid-fernet-token"), "")

    def test_mask(self):
        self.assertEqual(mask_key("sk-abcdefgh1234"), "sk-****1234")
        self.assertEqual(mask_key("short"), "****")
        self.assertEqual(mask_key(""), "")


class AIConfigApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _create(self, **extra):
        payload = {
            "name": "DeepSeek 主力",
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model_name": "deepseek-chat",
            "api_key": "sk-abcdefgh1234",
            **extra,
        }
        return self.client.post("/api/ai-configs/", payload, format="json")

    def test_create_returns_mask_not_plaintext(self):
        resp = self._create()
        self.assertEqual(resp.status_code, 201)
        body = resp.json()
        self.assertEqual(body["api_key_mask"], "sk-****1234")
        self.assertNotIn("sk-abcdefgh1234", str(body))
        # 库里是密文
        cfg = AIProviderConfig.objects.get(pk=body["id"])
        self.assertNotEqual(cfg.api_key_encrypted, "sk-abcdefgh1234")
        self.assertNotEqual(cfg.api_key_encrypted, "")

    def test_create_requires_key_except_ollama(self):
        resp = self.client.post(
            "/api/ai-configs/",
            {"name": "本地", "provider": "openai_compatible", "model_name": "x"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        resp2 = self.client.post(
            "/api/ai-configs/",
            {"name": "Ollama", "provider": "ollama", "model_name": "qwen",
             "base_url": "http://127.0.0.1:11434/v1"},
            format="json",
        )
        self.assertEqual(resp2.status_code, 201)

    def test_patch_empty_key_keeps_cipher(self):
        resp = self._create()
        cfg_id = resp.json()["id"]
        before = AIProviderConfig.objects.get(pk=cfg_id).api_key_encrypted
        resp2 = self.client.patch(
            f"/api/ai-configs/{cfg_id}/", {"model_name": "deepseek-reasoner", "api_key": ""},
            format="json",
        )
        self.assertEqual(resp2.status_code, 200)
        after = AIProviderConfig.objects.get(pk=cfg_id)
        self.assertEqual(after.api_key_encrypted, before)
        self.assertEqual(after.model_name, "deepseek-reasoner")

    def test_patch_new_key_updates_mask(self):
        resp = self._create()
        cfg_id = resp.json()["id"]
        self.client.patch(
            f"/api/ai-configs/{cfg_id}/", {"api_key": "sk-newkey9999xyz"},
            format="json",
        )
        cfg = AIProviderConfig.objects.get(pk=cfg_id)
        self.assertEqual(cfg.api_key_mask, "sk-****9xyz")
        self.assertEqual(decrypt_key(cfg.api_key_encrypted), "sk-newkey9999xyz")

    def test_default_mutex(self):
        r1 = self._create(name="A", is_default=True)
        r2 = self._create(name="B", is_default=True)
        self.assertTrue(AIProviderConfig.objects.get(pk=r2.json()["id"]).is_default)
        self.assertFalse(AIProviderConfig.objects.get(pk=r1.json()["id"]).is_default)

    def test_set_default_action(self):
        r1 = self._create(name="A", is_default=True)
        r2 = self._create(name="B")
        resp = self.client.post(f"/api/ai-configs/{r2.json()['id']}/set-default/", format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["is_default"])
        self.assertFalse(AIProviderConfig.objects.get(pk=r1.json()["id"]).is_default)

    def test_soft_delete(self):
        resp = self._create()
        cfg_id = resp.json()["id"]
        self.client.delete(f"/api/ai-configs/{cfg_id}/")
        self.assertEqual(AIProviderConfig.objects.count(), 0)
        self.assertEqual(AIProviderConfig.all_objects.count(), 1)

    def test_connection_no_base_url(self):
        resp = self._create(base_url="")
        cfg_id = resp.json()["id"]
        resp2 = self.client.post(f"/api/ai-configs/{cfg_id}/test/", format="json")
        self.assertEqual(resp2.status_code, 200)
        self.assertFalse(resp2.json()["ok"])
        self.assertIn("base_url", resp2.json()["error"])

    def test_connection_http_error(self):
        resp = self._create(base_url="http://127.0.0.1:59999/v1")
        cfg_id = resp.json()["id"]
        resp2 = self.client.post(f"/api/ai-configs/{cfg_id}/test/", format="json")
        self.assertEqual(resp2.status_code, 200)
        body = resp2.json()
        self.assertFalse(body["ok"])
        self.assertIn("error", body)
