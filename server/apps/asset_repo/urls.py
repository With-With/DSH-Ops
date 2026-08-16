from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ElementViewSet, PageObjectViewSet

app_name = "asset_repo"

router = DefaultRouter()
router.register(r"pages", PageObjectViewSet, basename="page")
router.register(r"elements", ElementViewSet, basename="element")

urlpatterns = [
    path("assets/", include(router.urls)),
]
