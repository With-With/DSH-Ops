from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AIProviderConfigViewSet

app_name = "ai_config"

router = DefaultRouter()
router.register(r"ai-configs", AIProviderConfigViewSet, basename="ai-config")

urlpatterns = [
    path("", include(router.urls)),
]
