"""
agent_runtime 序列化器。
"""
from rest_framework import serializers

from .models import AgentInvocation, ArtifactDraft


class AgentInvocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentInvocation
        fields = [
            "id",
            "stage",
            "task_set_id",
            "recording_id",
            "instruction",
            "instruction_sha",
            "output_text",
            "parsed_json",
            "status",
            "exit_code",
            "duration_ms",
            "mock",
            "error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ArtifactDraftSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArtifactDraft
        fields = [
            "id",
            "task_set_id",
            "kind",
            "content",
            "schema_version",
            "valid",
            "validation_errors",
            "status",
            "review_note",
            "invocation_id",
            "reviewed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class GatewayTestSerializer(serializers.Serializer):
    """gateway/test 调试接口的请求体。"""
    stage = serializers.CharField(max_length=64, required=True)
    instruction = serializers.CharField(required=True)
    mock = serializers.BooleanField(default=False)
    timeout = serializers.IntegerField(min_value=1, max_value=60, default=30)
