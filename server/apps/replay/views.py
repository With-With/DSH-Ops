import os

from django.http import FileResponse, Http404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import ReplayRun
from .runner import run_replay
from .serializers import ReplayCreateSerializer, ReplayRunSerializer


class ReplayRunViewSet(viewsets.GenericViewSet):
    """回放执行管理 ViewSet。"""

    queryset = ReplayRun.objects.all()
    serializer_class = ReplayRunSerializer
    lookup_field = "pk"

    def list(self, request):
        """GET /api/replays/ — 回放执行列表（分页）。"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """GET /api/replays/{id}/ — 回放执行详情。"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request):
        """POST /api/replays/ — 创建并同步执行回放。

        请求体: { recording_id, task_set_id?, headless? }
        同步执行完成后返回完整 ReplayRun 序列化结果。
        """
        serializer = ReplayCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        recording_id = serializer.validated_data["recording_id"]
        task_set_id = serializer.validated_data.get("task_set_id")
        headless = serializer.validated_data.get("headless")

        from apps.recorder.models import Recording
        try:
            recording = Recording.objects.get(pk=recording_id)
        except Recording.DoesNotExist:
            return Response(
                {"detail": f"Recording #{recording_id} 不存在"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            replay_run = run_replay(
                recording,
                task_set_id=task_set_id,
                headless=headless,
            )
        except Exception as e:
            return Response(
                {"detail": f"回放启动失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        out = ReplayRunSerializer(replay_run, context={"request": request, "view": self}).data
        return Response(out, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="trace/download")
    def trace_download(self, request, pk=None):
        """GET /api/replays/{id}/trace/download/ — 下载 trace.zip 文件。"""
        instance = self.get_object()
        trace_path = instance.trace_path
        if not trace_path or not os.path.exists(trace_path):
            raise Http404("Trace 文件不存在")

        response = FileResponse(
            open(trace_path, "rb"),
            content_type="application/zip",
            as_attachment=True,
            filename=f"replay_{instance.pk}_trace.zip",
        )
        return response
