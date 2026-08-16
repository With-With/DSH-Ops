from django.apps import AppConfig


class TasksetsConfig(AppConfig):
    """P1 - 任务集管理：测试任务的编排、调度与执行追踪。"""
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tasksets"
    verbose_name = "任务集"
