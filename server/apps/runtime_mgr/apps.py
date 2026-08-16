from django.apps import AppConfig


class RuntimeMgrConfig(AppConfig):
    """M1 RuntimeMgr 模块：DSH 运行时环境的检测、健康检查与删除管理。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.runtime_mgr"
    verbose_name = "运行时管理"
