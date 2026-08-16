import os
import threading

from django.db import connections
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
        """POST /api/replays/ — 创建并执行回放。

        请求体: { recording_id, task_set_id?, headless? }
        默认同步执行完成后返回完整 ReplayRun 序列化结果；
        `?async=1` 时立即返回 202（status=running），线程内执行，前端轮询
        GET /api/replays/<id>/ 至终态。
        """
        async_mode = request.query_params.get("async") == "1"
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

        if async_mode:
            # 预建 running 记录，线程内跑完回写；线程内重新 fetch（跨线程安全）
            replay_run = ReplayRun.objects.create(
                recording=recording,
                task_set_id=task_set_id,
                status="running",
                steps_total=0,
                steps_passed=0,
            )
            run_pk = replay_run.pk
            recording_pk = recording.pk

            def _async_run():
                try:
                    from apps.recorder.models import Recording as _Recording

                    rec = _Recording.objects.get(pk=recording_pk)
                    run = ReplayRun.objects.get(pk=run_pk)
                    run_replay(rec, task_set_id=task_set_id, headless=headless, replay_run=run)
                except Exception as exc:  # 兜底：绝不静默丢线程
                    try:
                        run = ReplayRun.objects.get(pk=run_pk)
                        run.status = "failed"
                        run.error = f"async replay error: {exc}"
                        run.save(update_fields=["status", "error", "updated_at"])
                    except Exception:
                        pass
                finally:
                    connections.close_all()

            threading.Thread(target=_async_run, daemon=True).start()
            out = ReplayRunSerializer(replay_run, context={"request": request, "view": self}).data
            return Response(out, status=status.HTTP_202_ACCEPTED)

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
