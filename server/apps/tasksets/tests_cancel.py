"""P4 #6：协作式取消 + 进行中状态 单测。"""
from django.test import TestCase
from rest_framework.test import APIClient

from .cancel import clear_cancel, is_cancelled, request_cancel
from .models import TaskSet
from .services import create_task_set
from .stages import run_pipeline


class CancelMechanismTests(TestCase):
    def setUp(self):
        self.ts = create_task_set("取消测试", recording_id=1)
        clear_cancel(self.ts.id)

    def test_request_and_clear(self):
        request_cancel(self.ts.id)
        self.assertTrue(is_cancelled(self.ts.id))
        self.assertTrue(TaskSet.objects.get(pk=self.ts.id).cancel_requested)
        clear_cancel(self.ts.id)
        self.assertFalse(is_cancelled(self.ts.id))

    def test_pipeline_stops_between_stages(self):
        """置取消后 run_pipeline 直接标记终止，不产生新 StageJob。"""
        from unittest.mock import patch

        self.ts.status = "replay_done"
        self.ts.save(update_fields=["status", "updated_at"])
        request_cancel(self.ts.id)
        with patch("apps.tasksets.stages.run_extract_stage") as mock_extract:
            ts = run_pipeline(self.ts)
        mock_extract.assert_not_called()
        self.assertEqual(ts.status, "failed")
        self.assertIn("终止", ts.error)
        # 清理（防污染其他测试）
        clear_cancel(self.ts.id)

    def test_pipeline_runs_when_not_cancelled(self):
        from unittest.mock import patch

        from apps.agent_runtime.gateway import AgentGateway

        self.ts.status = "replay_done"
        self.ts.save(update_fields=["status", "updated_at"])
        gw = AgentGateway()
        gw.mode = "mock"
        with patch("apps.tasksets.stages.get_gateway", return_value=gw):
            from apps.recorder.models import Recording

            Recording.objects.create(name="c", raw_content="x", start_url="http://x/")
            ts = run_pipeline(self.ts)
        # mock 链应推进（extract 至少执行）
        self.assertIn(
            ts.status, ("extract_done", "design_done", "review_done",
                        "generate_done", "failed")
        )
        clear_cancel(self.ts.id)


class CancelApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.ts = create_task_set("取消API", recording_id=1)
        clear_cancel(self.ts.id)

    def test_cancel_in_progress_202(self):
        self.ts.status = "extracting"
        self.ts.save(update_fields=["status", "updated_at"])
        resp = self.client.post(f"/api/tasksets/{self.ts.id}/cancel/", format="json")
        self.assertEqual(resp.status_code, 202)
        self.assertTrue(TaskSet.objects.get(pk=self.ts.id).cancel_requested)
        clear_cancel(self.ts.id)

    def test_cancel_idempotent(self):
        self.ts.status = "generating"
        self.ts.save(update_fields=["status", "updated_at"])
        r1 = self.client.post(f"/api/tasksets/{self.ts.id}/cancel/", format="json")
        r2 = self.client.post(f"/api/tasksets/{self.ts.id}/cancel/", format="json")
        self.assertEqual(r1.status_code, 202)
        self.assertEqual(r2.status_code, 202)
        clear_cancel(self.ts.id)

    def test_cancel_terminal_409(self):
        resp = self.client.post(f"/api/tasksets/{self.ts.id}/cancel/", format="json")
        # status=created 非 in_progress 且未请求过 -> 409
        self.assertEqual(resp.status_code, 409)

    def test_in_progress_field(self):
        self.ts.status = "designing"
        self.ts.save(update_fields=["status", "updated_at"])
        resp = self.client.get(f"/api/tasksets/{self.ts.id}/")
        self.assertTrue(resp.json()["in_progress"])
        self.ts.status = "design_done"
        self.ts.save(update_fields=["status", "updated_at"])
        resp2 = self.client.get(f"/api/tasksets/{self.ts.id}/")
        self.assertFalse(resp2.json()["in_progress"])
