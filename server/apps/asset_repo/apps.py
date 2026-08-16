from django.apps import AppConfig


class AssetRepoConfig(AppConfig):
    """P1 - 资源仓库：测试资源（截图、附件、脚本等）的存储与管理。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.asset_repo"
    verbose_name = "资源仓库"
