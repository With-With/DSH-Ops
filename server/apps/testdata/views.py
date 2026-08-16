from rest_framework import status, viewsets
from rest_framework.response import Response

from .models import ParameterSet
from .serializers import ParameterSetSerializer


class ParameterSetViewSet(viewsets.ModelViewSet):
    """参数集 CRUD。

    - GET 列表 / 详情：values 中 secret 键的值会被脱敏为 ${secret:<key>}
    - POST：允许明文入库（P1 不加密存储）
    - DELETE：软删除
    """

    queryset = ParameterSet.objects.all()
    serializer_class = ParameterSetSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()  # 软删除
        return Response(status=status.HTTP_204_NO_CONTENT)
