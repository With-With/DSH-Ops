from rest_framework import serializers

from .models import ReplayRun


class ReplayRunSerializer(serializers.ModelSerializer):
    """回放执行记录序列化器。"""

    trace_available = serializers.SerializerMethodField()
    trace_url = serializers.SerializerMethodField()
    recording_name = serializers.CharField(source="recording.name", read_only=True)
    video_available = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()

    class Meta:
        model = ReplayRun
        fields = [
            "id",
            "recording",
            "recording_name",
            "task_set_id",
            "status",
            "duration_ms",
            "steps_total",
            "steps_passed",
            "error",
            "trace_path",
            "trace_hash",
            "trace_available",
            "trace_url",
            "video_available",
            "video_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "duration_ms",
            "steps_total",
            "steps_passed",
            "error",
            "trace_path",
            "trace_hash",
            "trace_available",
            "trace_url",
            "video_available",
            "video_url",
            "recording_name",
            "created_at",
            "updated_at",
        ]

    def get_trace_available(self, obj):
        import os
        return bool(obj.trace_path and os.path.exists(obj.trace_path))

    def get_trace_url(self, obj):
        if not obj.trace_path:
            return ""
        request = self.context.get("request")
        if request is None:
            return f"/api/replays/{obj.pk}/trace/download/"
        return request.build_absolute_uri(f"/api/replays/{obj.pk}/trace/download/")

    def get_video_available(self, obj):
        import os
        return bool(obj.video_path and os.path.exists(obj.video_path))

    def get_video_url(self, obj):
        if not obj.video_path:
            return ""
        request = self.context.get("request")
        if request is None:
            return f"/api/replays/{obj.pk}/video/"
        return request.build_absolute_uri(f"/api/replays/{obj.pk}/video/")


class ReplayCreateSerializer(serializers.Serializer):
    """创建回放的请求序列化器。"""

    recording_id = serializers.IntegerField()
    task_set_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    headless = serializers.BooleanField(required=False, allow_null=True, default=None)
