from rest_framework import serializers

from .models import StageJob, TaskSet


class StageJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = StageJob
        fields = [
            "id",
            "stage",
            "status",
            "external_ref",
            "detail",
            "started_at",
            "finished_at",
            "created_at",
        ]
        read_only_fields = fields


class TaskSetSerializer(serializers.ModelSerializer):
    """列表/详情通用序列化器。详情时带嵌套 stage_jobs。"""

    stage_jobs = StageJobSerializer(many=True, read_only=True)

    class Meta:
        model = TaskSet
        fields = [
            "id",
            "name",
            "recording_id",
            "correlation_uuid",
            "status",
            "current_stage",
            "error",
            "created_at",
            "updated_at",
            "stage_jobs",
        ]
        read_only_fields = [
            "id",
            "correlation_uuid",
            "status",
            "current_stage",
            "error",
            "created_at",
            "updated_at",
            "stage_jobs",
        ]


class TaskSetCreateSerializer(serializers.ModelSerializer):
    """创建入参：name + recording_id"""

    class Meta:
        model = TaskSet
        fields = ["name", "recording_id"]
