from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TaskSetViewSet

app_name = "tasksets"

router = DefaultRouter()
router.register(r"tasksets", TaskSetViewSet, basename="taskset")

urlpatterns = [
    path("", include(router.urls)),
]
