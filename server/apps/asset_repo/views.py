from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from django_filters.rest_framework import DjangoFilterBackend

from .matching import match_element
from .models import Element, PageObject
from .serializers import (
    ElementQuerySerializer,
    ElementSerializer,
    PageObjectSerializer,
)


class PageObjectViewSet(viewsets.ModelViewSet):
    """页面对象 CRUD。软删：DELETE 走 BaseModel 的软删除逻辑。"""

    queryset = PageObject.objects.all()
    serializer_class = PageObjectSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    search_fields = ["name", "url_pattern"]
    # 只允许 GET/POST/DELETE（不提供 PATCH/PUT 简化 P1；如需再加）
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_queryset(self):
        # 软删的记录默认不可见（objects 是 SoftDeleteManager）
        return super().get_queryset()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()  # 软删除
        return Response(status=status.HTTP_204_NO_CONTENT)


class ElementViewSet(viewsets.ModelViewSet):
    """元素 CRUD + 查询入口。

    list 支持：
        - page_id 过滤
        - search 模糊匹配 name
    """

    queryset = Element.objects.all()
    serializer_class = ElementSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["role", "source"]
    search_fields = ["name", "notes"]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def filter_queryset(self, queryset):
        # 契约参数名 page_id（django-filter 生成的 FK 过滤参数是 page，这里统一成 page_id）
        queryset = super().filter_queryset(queryset)
        page_id = self.request.query_params.get("page_id")
        if page_id:
            queryset = queryset.filter(page_id=page_id)
        return queryset

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()  # 软删除
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["post"], url_path="query")
    def query(self, request):
        """search-first 查询入口：给定 URL + name + role (+snapshot_hash)，
        返回匹配结果（高/中/none 置信度 + 命中元素 + 候选）。

        这是 P2 A1/MCP 复用资产的核心入口。
        """
        serializer = ElementQuerySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = match_element(
            page_url=serializer.validated_data["page_url"],
            name=serializer.validated_data["name"],
            role=serializer.validated_data.get("role") or "",
            snapshot_hash=serializer.validated_data.get("snapshot_hash") or None,
        )
        return Response(result, status=status.HTTP_200_OK)
