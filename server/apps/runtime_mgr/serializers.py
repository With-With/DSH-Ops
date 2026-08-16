from rest_framework import serializers

from .models import RuntimeInstance
from .services import _list_profiles, _load_pinned_version


class RuntimeInstanceSerializer(serializers.ModelSerializer):
    """运行时实例序列化器。

    额外附加 profiles 和版本漂移信息，供列表/详情展示。
    """

    profiles = serializers.SerializerMethodField()
    pinned_version = serializers.SerializerMethodField()
    version_drift = serializers.SerializerMethodField()

    class Meta:
        model = RuntimeInstance
        fields = [
            "id",
            "name",
            "runtime_dir",
            "dsh_bin_path",
            "home_dir",
            "version",
            "node_version",
            "status",
            "last_check_at",
            "notes",
            "is_default",
            "created_at",
            "updated_at",
            # 附加字段
            "profiles",
            "pinned_version",
            "version_drift",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "last_check_at",
            "profiles",
            "pinned_version",
            "version_drift",
        ]

    def get_profiles(self, obj):
        return _list_profiles(obj.home_dir or "")

    def get_pinned_version(self, obj):
        return _load_pinned_version()

    def get_version_drift(self, obj):
        pinned = _load_pinned_version()
        if not pinned or not obj.version:
            return False
        return pinned != obj.version


class DetectSerializer(serializers.Serializer):
    """探测请求参数。"""
    runtime_dir = serializers.CharField(required=False, allow_blank=True, max_length=512)
    home_dir = serializers.CharField(required=False, allow_blank=True, max_length=512)


class DetectResultSerializer(serializers.Serializer):
    """探测结果序列化器（同时用于 upsert 后的实例 + 原始探测信息）。"""
    instance = RuntimeInstanceSerializer(read_only=True)
    created = serializers.BooleanField(read_only=True)
    detect_result = serializers.DictField(read_only=True)


class HealthCheckResultSerializer(serializers.Serializer):
    """健康检查结果。"""
    passed = serializers.BooleanField()
    exit_code = serializers.IntegerField(allow_null=True)
    stdout = serializers.CharField()
    stderr = serializers.CharField()
    profile_used = serializers.CharField()


class AuditLogSerializer(serializers.Serializer):
    """审计日志序列化器。"""
    id = serializers.IntegerField()
    action = serializers.CharField()
    target = serializers.CharField()
    detail = serializers.DictField()
    created_by = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()
