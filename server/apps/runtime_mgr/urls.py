from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RuntimeViewSet

router = DefaultRouter()
router.register(r"runtimes", RuntimeViewSet, basename="runtime")

urlpatterns = [
    path("", include(router.urls)),
]
