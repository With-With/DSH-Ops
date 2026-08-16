from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TestCaseViewSet

app_name = "testcases"

router = DefaultRouter()
router.register(r"testcases", TestCaseViewSet, basename="testcase")

urlpatterns = [
    path("", include(router.urls)),
]
