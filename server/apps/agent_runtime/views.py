"""
agent_runtime 视图：
- GET  /agent/invocations/         调用记录列表
- GET  /agent/drafts/              草案列表（支持过滤）
- GET  /agent/drafts/<id>/         草案详情
- POST /agent/gateway/test/        调试：直跑网关
"""
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .gateway import AgentGateway
from .models import AgentInvocation, ArtifactDraft
from .serializers import (
    AgentInvocationSerializer,
    ArtifactDraftSerializer,
    GatewayTestSerializer,
)


class AgentInvocationListView(generics.ListAPIView):
    """Agent 调用记录列表（只读）。"""
    queryset = AgentInvocation.objects.all()
    serializer_class = AgentInvocationSerializer
    filterset_fields = ["stage", "status", "task_set_id", "recording_id", "mock"]
    ordering_fields = ["created_at", "duration_ms"]
    ordering = ["-created_at"]


class ArtifactDraftListView(generics.ListAPIView):
    """草案列表（支持 task_set_id / kind / status 过滤）。"""
    queryset = ArtifactDraft.objects.all()
    serializer_class = ArtifactDraftSerializer
    filterset_fields = ["task_set_id", "kind", "status", "valid"]
    ordering_fields = ["created_at"]
    ordering = ["-created_at"]


class ArtifactDraftDetailView(generics.RetrieveAPIView):
    """草案详情。"""
    queryset = ArtifactDraft.objects.all()
    serializer_class = ArtifactDraftSerializer


class GatewayTestView(APIView):
    """
    调试接口：直跑 AgentGateway，方便前端联调。
    超时上限 60s，避免长时间阻塞。
    """

    def post(self, request):
        serializer = GatewayTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        stage = serializer.validated_data["stage"]
        instruction = serializer.validated_data["instruction"]
        mock = serializer.validated_data["mock"]
        timeout = serializer.validated_data["timeout"]

        gw = AgentGateway()
        # 强制 mock 模式：通过环境变量覆盖（仅本次调用通过实例属性模拟不可行，
        # 因为 AgentGateway 初始化时读环境变量；这里用 patch 方式更干净）
        original_mode = gw.mode
        if mock:
            gw.mode = "mock"

        try:
            inv = gw.run_stage(stage, instruction, timeout=timeout)
        finally:
            gw.mode = original_mode

        return Response(
            AgentInvocationSerializer(inv).data,
            status=status.HTTP_200_OK,
        )
