"""ai_config 序列化器：永不回传明文密钥。"""
from rest_framework import serializers

from .crypto import encrypt_key, mask_key
from .models import AIProviderConfig


class AIProviderConfigSerializer(serializers.ModelSerializer):
    # 明文只写不读：创建/更新时接收 api_key，输出只有 mask
    api_key = serializers.CharField(
        write_only=True, required=False, allow_blank=True,
        max_length=512, help_text="编辑时留空表示不修改",
    )

    class Meta:
        model = AIProviderConfig
        fields = [
            "id", "name", "provider", "base_url", "model_name",
            "api_key",  # write_only
            "api_key_mask", "enabled", "is_default", "extra", "remark",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "api_key_mask", "created_at", "updated_at"]

    def validate(self, attrs):
        # 创建时必须有 api_key（除 ollama 本地部署）
        if self.instance is None and not attrs.get("api_key"):
            if attrs.get("provider") != "ollama":
                raise serializers.ValidationError(
                    {"api_key": "创建时必须提供 API Key（Ollama 本地部署除外）"}
                )
        return attrs

    def _apply_key(self, validated_data, instance=None):
        plain = validated_data.pop("api_key", None)
        if plain:  # 空串/None = 不修改（更新时）
            validated_data["api_key_encrypted"] = encrypt_key(plain)
            validated_data["api_key_mask"] = mask_key(plain)

    def create(self, validated_data):
        self._apply_key(validated_data)
        instance = super().create(validated_data)
        if instance.is_default:
            AIProviderConfig.objects.exclude(pk=instance.pk).update(is_default=False)
        return instance

    def update(self, instance, validated_data):
        self._apply_key(validated_data)
        instance = super().update(instance, validated_data)
        if instance.is_default:
            AIProviderConfig.objects.exclude(pk=instance.pk).update(is_default=False)
        return instance
