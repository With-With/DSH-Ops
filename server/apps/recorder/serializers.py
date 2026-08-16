from rest_framework import serializers

from .models import Recording
from .parser import parse_recording


class RecordingSerializer(serializers.ModelSerializer):
    """录制脚本序列化器。"""

    actions = serializers.SerializerMethodField()

    class Meta:
        model = Recording
        fields = [
            "id",
            "name",
            "language",
            "framework",
            "start_url",
            "raw_content",
            "normalized_content",
            "locators_count",
            "actions_count",
            "warnings",
            "actions",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "language",
            "framework",
            "start_url",
            "normalized_content",
            "locators_count",
            "actions_count",
            "warnings",
            "actions",
            "created_at",
            "updated_at",
        ]

    def get_actions(self, obj):
        """详情时返回动作序列（列表视图不返回以节省带宽）。"""
        # 判断是否是列表视图：通过 context 里的 view 动作
        view = self.context.get("view")
        if view and view.action == "list":
            return None
        try:
            result = parse_recording(obj.raw_content)
            return result["actions"]
        except Exception:
            return []


class RecordingCreateSerializer(serializers.Serializer):
    """创建录制的请求序列化器。"""

    name = serializers.CharField(max_length=128)
    content = serializers.CharField()
    filename = serializers.CharField(required=False, allow_blank=True, max_length=256, default="")

    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("脚本内容不能为空")
        return value
