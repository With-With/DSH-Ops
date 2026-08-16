"""
reviews 评审中心：对 agent_runtime 的产物草案（POM / Matrix）做人工评审。

- GET  /reviews/drafts/                   草案列表（kind/status 过滤，分页）
- POST /reviews/drafts/<id>/approve/      通过（终态，可带 note）
- POST /reviews/drafts/<id>/reject/       驳回（终态，可带 note）

评审后的草案进入终态（approved/rejected），再次评审返回 409。
"""
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView


def _get_artifact_draft_model():
    # 跨 app 运行期 lazy import（agent_runtime 并行开发期契约约定）
    from apps.agent_runtime.models import ArtifactDraft

    return ArtifactDraft


class ReviewDraftSerializer(serializers.Serializer):
    """草案评审序列化（显式字段，避免动态 Meta 的 DRF 缓存陷阱）。"""

    id = serializers.IntegerField(read_only=True)
    task_set_id = serializers.IntegerField(read_only=True, allow_null=True)
    kind = serializers.CharField(read_only=True)
    content = serializers.JSONField(read_only=True)
    schema_version = serializers.CharField(read_only=True)
    valid = serializers.BooleanField(read_only=True)
    validation_errors = serializers.JSONField(read_only=True)
    status = serializers.CharField(read_only=True)
    review_note = serializers.CharField(read_only=True)
    invocation_id = serializers.IntegerField(read_only=True, allow_null=True)
    reviewed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)


class DraftListView(generics.ListAPIView):
    """草案列表：GET /reviews/drafts/?kind=&status="""

    serializer_class = ReviewDraftSerializer

    def get_queryset(self):
        qs = _get_artifact_draft_model().objects.all()
        kind = self.request.query_params.get("kind")
        if kind:
            qs = qs.filter(kind=kind)
        task_set_id = self.request.query_params.get("task_set_id")
        if task_set_id:
            qs = qs.filter(task_set_id=task_set_id)
        return qs


class DraftReviewActionView(APIView):
    """通过/驳回：POST /reviews/drafts/<id>/approve|reject/"""

    action = None  # 子类设置

    def post(self, request, pk):
        model = _get_artifact_draft_model()
        try:
            draft = model.objects.get(pk=pk)
        except model.DoesNotExist:
            return Response({"detail": "草案不存在"}, status=status.HTTP_404_NOT_FOUND)

        if draft.status != "draft":
            return Response(
                {"detail": f"草案已是终态（{draft.status}），不可重复评审"},
                status=status.HTTP_409_CONFLICT,
            )

        note = (request.data or {}).get("note", "")
        draft.status = "approved" if self.action == "approve" else "rejected"
        draft.review_note = note
        draft.reviewed_at = timezone.now()
        draft.save(update_fields=["status", "review_note", "reviewed_at", "updated_at"])

        return Response(ReviewDraftSerializer(draft).data, status=status.HTTP_200_OK)


class DraftApproveView(DraftReviewActionView):
    action = "approve"


class DraftRejectView(DraftReviewActionView):
    action = "reject"
