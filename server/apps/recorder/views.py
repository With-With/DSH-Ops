from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Recording
from .parser import parse_recording
from .serializers import RecordingCreateSerializer, RecordingSerializer


class RecordingViewSet(viewsets.GenericViewSet):
    """录制脚本管理 ViewSet。"""

    queryset = Recording.objects.all()
    serializer_class = RecordingSerializer
    lookup_field = "pk"

    def list(self, request):
        """GET /api/recordings/ — 录制脚本列表（分页）。"""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        """GET /api/recordings/{id}/ — 录制脚本详情（含 normalized 与 actions）。"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def create(self, request):
        """POST /api/recordings/ — 创建录制（服务端 parse 后落库）。"""
        serializer = RecordingCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data["name"]
        content = serializer.validated_data["content"]
        filename = serializer.validated_data.get("filename", "") or ""

        result = parse_recording(content, filename=filename)

        recording = Recording.objects.create(
            name=name,
            language=result["language"],
            framework=result["framework"],
            start_url=result["start_url"],
            raw_content=content,
            normalized_content=result["normalized_content"],
            locators_count=result["locators_count"],
            actions_count=result["actions_count"],
            warnings=result["warnings"],
            created_by=request.user if request.user.is_authenticated else None,
        )

        out = RecordingSerializer(recording, context={"view": self}).data
        # 详情里也附上 actions（通过 get_actions 在 retrieve 模式返回，这里显式补上）
        out["actions"] = result["actions"]
        return Response(out, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        """DELETE /api/recordings/{id}/ — 软删除录制脚本。"""
        instance = self.get_object()
        instance.delete()
        return Response(
            {"detail": "删除成功"},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="actions")
    def actions_list(self, request, pk=None):
        """GET /api/recordings/{id}/actions/ — 获取动作序列。"""
        instance = self.get_object()
        try:
            result = parse_recording(instance.raw_content)
            return Response({"actions": result["actions"]})
        except Exception as e:
            return Response(
                {"detail": f"解析失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # ------------------------------------------------------------------
    # P4：codegen 浏览器录制 + AI 重组
    # ------------------------------------------------------------------

    @action(detail=False, methods=["post"], url_path="codegen/start")
    def codegen_start(self, request):
        """POST /api/recordings/codegen/start/ — 打开浏览器开始交互录制。"""
        from .codegen import get_status, start_session

        if get_status()["active"]:
            return Response(
                {"detail": "已有录制会话进行中，请先结束"},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            session = start_session(
                name=(request.data or {}).get("name", ""),
                start_url=(request.data or {}).get("start_url", ""),
            )
        except Exception as exc:  # Popen/环境异常 -> 友好 500 而非裸异常
            from apps.core.models import AuditLog

            AuditLog.objects.create(
                action="codegen.start_error",
                detail=f"{type(exc).__name__}: {exc}",
            )
            return Response(
                {"detail": f"启动录制器失败：{type(exc).__name__}: {exc}，"
                          "请确认 playwright 可用（配置中心可安装）"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                "session_id": session["session_id"],
                "name": session["name"],
                "start_url": session["start_url"],
                "started_at": session["started_at"],
                "tip": "浏览器已打开，请操作；完成后调用 stop 结束并保存",
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=False, methods=["get"], url_path="codegen/status")
    def codegen_status(self, request):
        """GET /api/recordings/codegen/status/ — 录制会话状态。"""
        from .codegen import get_status

        return Response(get_status())

    @action(detail=False, methods=["post"], url_path="codegen/stop")
    def codegen_stop(self, request):
        """POST /api/recordings/codegen/stop/ — 结束录制并保存（可自动 AI 分析）。

        session_id 可不传：为空时取当前活跃会话（单会话语义）。
        """
        from .codegen import get_status, stop_session

        session_id = (request.data or {}).get("session_id", "") or ""
        if not session_id:
            status_info = get_status()
            session_id = status_info.get("session_id", "") if status_info.get("active") else ""
        if not session_id:
            return Response(
                {"detail": "没有进行中的录制会话，无需结束"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            result = stop_session(
                session_id,
                auto_analyze=bool((request.data or {}).get("auto_analyze", False)),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="normalize")
    def normalize(self, request, pk=None):
        """POST /api/recordings/{id}/normalize/ — AI 重组为标准脚本（异步 202）。"""
        from .codegen import normalize_is_running
        from .normalizer import normalize_recording

        instance = self.get_object()
        if normalize_is_running(instance.id):
            return Response(
                {"detail": "该录制正在 AI 重组中"}, status=status.HTTP_409_CONFLICT
            )

        def _worker():
            from django.db import connections

            try:
                normalize_recording(instance)
            except Exception:
                pass
            finally:
                connections.close_all()

        import threading

        threading.Thread(
            target=_worker, daemon=True, name=f"recorder-normalize-{instance.id}"
        ).start()
        return Response(
            {"recording_id": instance.id, "status": "running"},
            status=status.HTTP_202_ACCEPTED,
        )
