from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReplayRunViewSet
from .views_demo import DemoLoginView

router = DefaultRouter()
router.register(r"replays", ReplayRunViewSet, basename="replay")

urlpatterns = [
    path("", include(router.urls)),
    # 演示登录页（供回放冒烟测试使用）
    path("demo/login/", DemoLoginView.as_view(), name="demo_login"),
]
