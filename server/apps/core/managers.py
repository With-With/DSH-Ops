from django.db import models


class SoftDeleteManager(models.Manager):
    """软删除管理器：默认过滤 is_deleted=False 的记录。"""

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def all_with_deleted(self):
        """返回包含已删除记录的查询集。"""
        return super().get_queryset()
