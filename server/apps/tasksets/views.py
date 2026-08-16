from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import TaskSet
from .serializers import TaskSetCreateSerializer, TaskSetSerializer
from .services import run_replay_stage


class TaskSetViewSet(viewsets.ReadOnlyModelViewSet):
    """任务集：列表 + 详情（含嵌套 stage_jobs）。

    创建接口走 create（POST），会同步执行 replay 阶段再返回。
    """

    queryset = TaskSet.objects.all()
    serializer_class = TaskSetSerializer
    # 只允许 GET 列表 / 详情 和 POST 创建
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        # 列表时不带 stage_jobs（省 N+1；详情再预取）
        qs = super().get_queryset()
        if self.action == "retrieve":
            qs = qs.prefetch_related("stage_jobs")
        return qs

    def create(self, request, *args, **kwargs):
        """创建 TaskSet 并同步执行 replay 阶段。

        注意：replay 可能耗时 30~90s，调用方应做好超时准备。
        若 replay 服务不可用（A 未完成 / 未装 playwright），
        会优雅降级：TaskSet 落库，StageJob 标 failed，
        HTTP 201 返回任务集 + 错误说明，不抛 500。
        """
        serializer = TaskSetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task_set = serializer.save(status="created")

        # 同步执行 replay 阶段
        task_set = run_replay_stage(task_set)

        # 重新序列化（带 stage_jobs）
        out = TaskSetSerializer(instance=task_set)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="stages")
    def run_stage(self, request, pk=None):
        """POST /api/tasksets/<id>/stages/ — 异步触发 A1/A2 阶段。

        body: {stage: "extract"|"design"}
        守卫通过 -> 202（status=extracting/designing，前端轮询详情）；
        守卫失败/阶段进行中 -> 409。
        """
        from .stages import run_stage_async

        stage = (request.data or {}).get("stage")
        if stage not in ("extract", "design"):
            return Response(
                {"detail": "stage 必须是 extract 或 design"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        task_set = self.get_object()
        try:
            task_set = run_stage_async(task_set, stage)
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "status": task_set.status},
                status=status.HTTP_409_CONFLICT,
            )

        out = TaskSetSerializer(instance=task_set)
        return Response(out.data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["post"], url_path="pipeline")
    def run_pipeline(self, request, pk=None):
        """POST /api/tasksets/<id>/pipeline/ — 一键流水线（异步）。

        replay -> extract -> design -> review -> generate 顺序执行，
        任一步失败即停（StageJob 留痕）。202 后前端轮询详情。
        """
        from .stages import run_pipeline_async

        task_set = self.get_object()
        try:
            task_set = run_pipeline_async(task_set)
        except ValueError as exc:
            return Response(
                {"detail": str(exc), "status": task_set.status},
                status=status.HTTP_409_CONFLICT,
            )

        out = TaskSetSerializer(instance=task_set)
        return Response(out.data, status=status.HTTP_202_ACCEPTED)
