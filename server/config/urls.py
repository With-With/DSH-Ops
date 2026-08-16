"""
URL configuration for DSH-Ops project.
"""
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("api/admin/", admin.site.urls),
    path("api/", include("apps.runtime_mgr.urls")),
]
