"""testcases 视图：用例管理 CRUD。"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import TestCase
from .serializers import TestCaseSerializer


class TestCaseViewSet(viewsets.ModelViewSet):
    """用例管理：AI 重组产出的 POM pytest 脚本。"""

    queryset = TestCase.objects.all()
    serializer_class = TestCaseSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def perform_destroy(self, instance):
        instance.delete()  # 软删

    @action(detail=False, methods=["post"], url_path="bulk-delete")
    def bulk_delete(self, request):
        """POST /api/testcases/bulk-delete/ {ids: [1,2]} - 软删多条用例。"""
        from apps.core.models import AuditLog

        ids = (request.data or {}).get("ids") or []
        if not isinstance(ids, list) or not ids:
            return Response(
                {"detail": "ids 必须是非空数组"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        count = 0
        for tc in self.get_queryset().filter(pk__in=ids):
            tc.delete()
            count += 1
        AuditLog.objects.create(
            action="testcase.bulk_delete",
            detail=f"批量删除用例 {count} 条（ids={ids}）",
        )
        return Response({"deleted": count})
