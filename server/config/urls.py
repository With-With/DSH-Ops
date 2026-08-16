"""
URL configuration for DSH-Ops project.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/admin/", admin.site.urls),
    path("api/", include("apps.runtime_mgr.urls")),
    path("api/", include("apps.recorder.urls")),
    path("api/", include("apps.replay.urls")),
    path("api/", include("apps.asset_repo.urls")),
    path("api/", include("apps.tasksets.urls")),
    path("api/", include("apps.testdata.urls")),
    path("api/", include("apps.agent_runtime.urls")),
    path("api/", include("apps.reviews.urls")),
    path("api/", include("apps.obs_center.urls")),
    path("api/", include("apps.ai_config.urls")),
    path("api/", include("apps.testcases.urls")),
]
