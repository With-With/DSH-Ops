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
