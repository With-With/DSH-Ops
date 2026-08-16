from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ParameterSetViewSet

app_name = "testdata"

router = DefaultRouter()
router.register(r"params", ParameterSetViewSet, basename="paramset")

urlpatterns = [
    path("testdata/", include(router.urls)),
]
