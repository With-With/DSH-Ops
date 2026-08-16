"""ai_config 视图：CRUD + 连通性测试 + 设为默认。"""
import json
import time
import urllib.error
import urllib.request

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import AuditLog

from .crypto import decrypt_key
from .models import AIProviderConfig
from .serializers import AIProviderConfigSerializer


class AIProviderConfigViewSet(viewsets.ModelViewSet):
    """AI 模型配置：密钥加密落库，只回掩码。"""

    queryset = AIProviderConfig.objects.all()
    serializer_class = AIProviderConfigSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_destroy(self, instance):
        instance.delete()  # 软删（BaseModel）
        AuditLog.objects.create(
            action="ai_config.delete",
            detail=f"删除 AI 配置 #{instance.pk} {instance.name}",
        )

    @action(detail=True, methods=["post"], url_path="test")
    def test_connection(self, request, pk=None):
        """连通性测试：POST /api/ai-configs/<id>/test/

        用配置的 base_url + model + key 发一条最小 chat 请求（标准库 urllib，
        超时 15s）。key 只在本次请求使用，不回传。
        """
        cfg = self.get_object()
        base = (cfg.base_url or "").rstrip("/")
        if not base:
            return Response(
                {"ok": False, "error": "未配置 base_url"},
                status=status.HTTP_200_OK,
            )

        api_key = decrypt_key(cfg.api_key_encrypted)
        url = f"{base}/chat/completions"
        payload = json.dumps({
            "model": cfg.model_name,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
            "stream": False,
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        start = time.time()
        try:
            req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                latency = int((time.time() - start) * 1000)
                result = {"ok": True, "status_code": resp.status, "latency_ms": latency}
        except urllib.error.HTTPError as e:
            latency = int((time.time() - start) * 1000)
            result = {
                "ok": False, "status_code": e.code, "latency_ms": latency,
                "error": f"HTTP {e.code}: {e.reason}",
            }
        except Exception as e:
            result = {"ok": False, "error": f"{type(e).__name__}: {e}"}

        AuditLog.objects.create(
            action="ai_config.test",
            detail=f"连通性测试 #{cfg.pk} {cfg.name}: ok={result.get('ok')}",
        )
        return Response(result)

    @action(detail=True, methods=["post"], url_path="set-default")
    def set_default(self, request, pk=None):
        cfg = self.get_object()
        AIProviderConfig.objects.exclude(pk=cfg.pk).update(is_default=False)
        cfg.is_default = True
        cfg.save(update_fields=["is_default", "updated_at"])
        AuditLog.objects.create(
            action="ai_config.set_default",
            detail=f"设为默认 #{cfg.pk} {cfg.name}",
        )
        return Response(AIProviderConfigSerializer(cfg).data)
