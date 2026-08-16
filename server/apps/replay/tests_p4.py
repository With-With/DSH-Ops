"""P4 #7：回放视频 + 批量删除 单测。"""
import os
import tempfile

from django.test import TestCase
from rest_framework.test import APIClient

from apps.recorder.models import Recording

from .models import ReplayRun


def _mk_recording():
    return Recording.objects.create(
        name="video-录制",
        raw_content="from playwright.sync_api import sync_playwright\n",
    )


def _mk_run(rec, video=True):
    run = ReplayRun.objects.create(
        recording=rec, status="success", steps_total=3, steps_passed=3,
    )
    if video:
        tmp = tempfile.NamedTemporaryFile(suffix=".webm", delete=False)
        tmp.write(b"\x1a\x45\xdf\xa3fake-webm-bytes")
        tmp.close()
        run.video_path = tmp.name
        run.save(update_fields=["video_path", "updated_at"])
    return run


class VideoAndBulkDeleteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.rec = _mk_recording()
        self.run = _mk_run(self.rec)
        self.run2 = _mk_run(self.rec, video=False)

    def tearDown(self):
        for r in ReplayRun.objects.all():
            if r.video_path and os.path.exists(r.video_path):
                try:
                    os.remove(r.video_path)
                except OSError:
                    pass

    def test_serializer_video_fields(self):
        resp = self.client.get("/api/replays/")
        results = resp.json()["results"]
        by_id = {r["id"]: r for r in results}
        self.assertTrue(by_id[self.run.id]["video_available"])
        self.assertIn(f"/api/replays/{self.run.id}/video/", by_id[self.run.id]["video_url"])
        self.assertFalse(by_id[self.run2.id]["video_available"])
        self.assertEqual(by_id[self.run2.id]["video_url"], "")

    def test_video_stream_200(self):
        resp = self.client.get(f"/api/replays/{self.run.id}/video/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("video/webm", resp["Content-Type"])
        self.assertIn(b"fake-webm", b"".join(resp.streaming_content))

    def test_video_missing_404(self):
        resp = self.client.get(f"/api/replays/{self.run2.id}/video/")
        self.assertEqual(resp.status_code, 404)

    def test_bulk_delete(self):
        resp = self.client.post(
            "/api/replays/bulk-delete/", {"ids": [self.run.id, self.run2.id]},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted"], 2)
        self.assertEqual(ReplayRun.objects.count(), 0)
        self.assertEqual(ReplayRun.all_objects.count(), 2)

    def test_bulk_delete_empty_400(self):
        resp = self.client.post("/api/replays/bulk-delete/", {"ids": []}, format="json")
        self.assertEqual(resp.status_code, 400)

    def test_bulk_delete_nonexistent(self):
        resp = self.client.post("/api/replays/bulk-delete/", {"ids": [99999]}, format="json")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["deleted"], 0)
