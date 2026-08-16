"""
obs_center 观测中心：跨 app 聚合执行观测数据（只读）。

- GET /api/obs/overview/   总览统计（调用/回放/阶段/生成 数量与耗时）
- GET /api/obs/activity/   最近活动流（合并各来源，按时间倒序）
"""
from collections import Counter

from django.db.models import Avg
from rest_framework.response import Response
from rest_framework.views import APIView


def _stats_for(model, status_field="status", duration_field="duration_ms"):
    qs = model.objects.all()
    stats = {
        "total": qs.count(),
        "by_status": dict(Counter(qs.values_list(status_field, flat=True))),
    }
    if duration_field:
        stats["avg_duration_ms"] = round(
            qs.aggregate(avg=Avg(duration_field))["avg"] or 0, 1
        )
    return stats


class OverviewView(APIView):
    """GET /api/obs/overview/"""

    def get(self, request):
        from apps.agent_runtime.models import AgentInvocation  # type: ignore
        from apps.replay.models import ReplayRun  # type: ignore
        from apps.tasksets.models import GeneratedRun, StageJob  # type: ignore

        inv_qs = AgentInvocation.objects.all()
        inv_by_stage = Counter(inv_qs.values_list("stage", flat=True))

        stage_qs = StageJob.objects.all()
        stage_by_stage = Counter(stage_qs.values_list("stage", flat=True))

        gen_qs = GeneratedRun.objects.all()

        data = {
            "invocations": {
                **_stats_for(AgentInvocation),
                "by_stage": dict(inv_by_stage),
                "mock_count": inv_qs.filter(mock=True).count(),
            },
            "replays": _stats_for(ReplayRun),
            "stages": {
                **_stats_for(StageJob, duration_field=None),
                "by_stage": dict(stage_by_stage),
            },
            "generated": {
                "total": gen_qs.count(),
                "by_status": dict(Counter(gen_qs.values_list("status", flat=True))),
                "pass_rate": (
                    round(
                        gen_qs.filter(status="pass").count() / gen_qs.count() * 100, 1
                    )
                    if gen_qs.count()
                    else None
                ),
            },
        }
        return Response(data)


class ActivityView(APIView):
    """GET /api/obs/activity/?limit=50 最近活动流。"""

    def get(self, request):
        from apps.agent_runtime.models import AgentInvocation  # type: ignore
        from apps.replay.models import ReplayRun  # type: ignore
        from apps.tasksets.models import GeneratedRun, StageJob  # type: ignore

        limit = min(int(request.query_params.get("limit", 50)), 200)

        events = []
        for inv in AgentInvocation.objects.all()[:100]:
            events.append(
                {
                    "at": inv.created_at.isoformat(),
                    "type": "invocation",
                    "stage": inv.stage,
                    "status": inv.status,
                    "detail": f"{'mock' if inv.mock else 'real'} · {inv.duration_ms}ms"
                    + (f" · {inv.error[:80]}" if inv.error else ""),
                    "ref_id": inv.id,
                }
            )
        for rp in ReplayRun.objects.all()[:100]:
            events.append(
                {
                    "at": rp.created_at.isoformat(),
                    "type": "replay",
                    "stage": "replay",
                    "status": rp.status,
                    "detail": f"{rp.steps_passed}/{rp.steps_total} 步"
                    + (f" · {rp.error[:80]}" if rp.error else ""),
                    "ref_id": rp.id,
                }
            )
        for sj in StageJob.objects.all()[:100]:
            events.append(
                {
                    "at": sj.created_at.isoformat(),
                    "type": "stage",
                    "stage": sj.stage,
                    "status": sj.status,
                    "detail": f"task_set={sj.task_set_id}"
                    + (f" · {str(sj.detail.get('error'))[:80]}" if sj.detail.get("error") else ""),
                    "ref_id": sj.id,
                }
            )
        for gr in GeneratedRun.objects.all()[:100]:
            events.append(
                {
                    "at": gr.created_at.isoformat(),
                    "type": "generated",
                    "stage": "generate",
                    "status": gr.status,
                    "detail": f"{gr.script_file} · {gr.rounds} 轮",
                    "ref_id": gr.id,
                }
            )

        events.sort(key=lambda e: e["at"], reverse=True)
        return Response({"results": events[:limit], "count": len(events)})
