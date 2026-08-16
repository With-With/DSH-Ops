from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import RuntimeInstance
from .serializers import (
    AuditLogSerializer,
    DetectResultSerializer,
    DetectSerializer,
    HealthCheckResultSerializer,
    RuntimeInstanceSerializer,
)
from .services import (
    delete_runtime,
    detect_runtime,
    get_audit_logs_for_instance,
    health_check,
    upsert_runtime_from_detect,
)


class RuntimeViewSet(viewsets.GenericViewSet):
    """运行时实例管理 ViewSet。

    仅实现任务要求的端点，列表用 GET list，详情用 GET retrieve。
    """

    queryset = RuntimeInstance.objects.all()
    serializer_class = RuntimeInstanceSerializer
    lookup_field = "pk"

    def list(self, request):
        """GET /api/runtimes/ — 运行时实例列表。"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """GET /api/runtimes/{id}/ — 运行时实例详情。"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="detect")
    def detect(self, request):
        """POST /api/runtimes/detect/ — 探测运行时环境并 upsert。"""
        serializer = DetectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        runtime_dir = serializer.validated_data.get("runtime_dir") or None
        home_dir = serializer.validated_data.get("home_dir") or None

        detect_result = detect_runtime(runtime_dir=runtime_dir, home_dir=home_dir)
        instance, created = upsert_runtime_from_detect(
            detect_result,
            user=request.user if request.user.is_authenticated else None,
        )

        result = {
            "instance": RuntimeInstanceSerializer(instance).data,
            "created": created,
            "detect_result": detect_result,
        }
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="health_check")
    def health_check_action(self, request, pk=None):
        """POST /api/runtimes/{id}/health_check/ — 健康检查。"""
        instance = self.get_object()
        detail = health_check(instance)
        return Response(detail, status=status.HTTP_200_OK)

    def destroy(self, request, pk=None):
        """DELETE /api/runtimes/{id}/?physical=false&delete_home=false — 删除。"""
        instance = self.get_object()
        physical = request.query_params.get("physical", "false").lower() == "true"
        delete_home = request.query_params.get("delete_home", "false").lower() == "true"

        success, reason = delete_runtime(
            instance,
            physical=physical,
            delete_home=delete_home,
            user=request.user if request.user.is_authenticated else None,
        )

        if not success:
            return Response(
                {"detail": reason or "删除被拒绝"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"detail": "删除成功", "physical": physical, "delete_home": delete_home},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="audit")
    def audit_logs(self, request, pk=None):
        """GET /api/runtimes/{id}/audit/ — 审计日志。"""
        instance = self.get_object()
        logs = get_audit_logs_for_instance(instance)
        page = self.paginate_queryset(logs)
        if page is not None:
            data = [
                {
                    "id": log.id,
                    "action": log.action,
                    "target": log.target,
                    "detail": log.detail,
                    "created_by": log.created_by.username if log.created_by else None,
                    "created_at": log.created_at,
                }
                for log in page
            ]
            return self.get_paginated_response(data)
        data = [
            {
                "id": log.id,
                "action": log.action,
                "target": log.target,
                "detail": log.detail,
                "created_by": log.created_by.username if log.created_by else None,
                "created_at": log.created_at,
            }
            for log in logs
        ]
        return Response(data, status=status.HTTP_200_OK)
