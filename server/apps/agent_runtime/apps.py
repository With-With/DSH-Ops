from django.apps import AppConfig


class AgentRuntimeConfig(AppConfig):
    """P2 - Agent 运行时编排：管理 DSH agent 的启动/停止/会话。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agent_runtime"
    verbose_name = "Agent 运行时"
