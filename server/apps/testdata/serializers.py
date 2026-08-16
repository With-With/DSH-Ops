from rest_framework import serializers

from .models import ParameterSet


def _mask_secret_values(values: dict, secret_keys: list) -> dict:
    """把 values 中命中 secret_keys 的键值替换为 ${secret:<key>} 占位符。

    与 contracts/matrix.schema.json 的约定保持一致。
    """
    if not secret_keys:
        return values
    masked = dict(values) if values else {}
    for key in secret_keys:
        if key in masked:
            masked[key] = f"${{secret:{key}}}"
    return masked


class ParameterSetSerializer(serializers.ModelSerializer):
    """参数集序列化器。

    - 输出时：values 中命中 secret_keys 的值会被替换为 ${secret:<key>}
    - 输入时：允许明文（P1 不加密存储，P3 再做）
    """

    class Meta:
        model = ParameterSet
        fields = [
            "id",
            "name",
            "values",
            "secret_keys",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance):
        """序列化输出时对 secret 值做脱敏。"""
        data = super().to_representation(instance)
        # 注意：instance.values 是原始值（明文），脱敏只在输出层
        data["values"] = _mask_secret_values(instance.values, instance.secret_keys)
        return data

    def validate_secret_keys(self, value):
        """校验 secret_keys 是字符串列表。"""
        if not isinstance(value, list):
            raise serializers.ValidationError("secret_keys must be a list")
        for item in value:
            if not isinstance(item, str):
                raise serializers.ValidationError("each secret key must be a string")
        return value

    def validate_values(self, value):
        """校验 values 是 dict。"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("values must be an object/dict")
        return value
