from rest_framework import serializers

from .models import Element, PageObject


class PageObjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = PageObject
        fields = [
            "id",
            "name",
            "url_pattern",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_url_pattern(self, value):
        # search-first 纪律：同一 url_pattern 不允许重复建档，防止 match_page 二义性。
        # 已存在时提示复用已有页面（这正是"先搜后建"该走的路径）。
        qs = PageObject.objects.filter(url_pattern=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        existing = qs.first()
        if existing:
            raise serializers.ValidationError(
                f"url_pattern 已存在（页面 id={existing.pk}, name={existing.name}）："
                f"请复用该页面而非重复创建"
            )
        return value


class ElementSerializer(serializers.ModelSerializer):
    # 契约字段名 page_id（前端/matching/MCP 均用此名）；映射到 FK page
    page_id = serializers.PrimaryKeyRelatedField(
        source="page", queryset=PageObject.objects.all()
    )

    class Meta:
        model = Element
        fields = [
            "id",
            "page_id",
            "name",
            "role",
            "candidates",
            "snapshot_hash",
            "source",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ElementQuerySerializer(serializers.Serializer):
    """元素查询入参：POST /assets/elements/query/"""

    page_url = serializers.CharField(max_length=1024)
    name = serializers.CharField(max_length=128)
    role = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    snapshot_hash = serializers.CharField(
        max_length=128, required=False, allow_blank=True, default=None
    )
