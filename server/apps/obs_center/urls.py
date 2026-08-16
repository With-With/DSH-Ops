from django.urls import path

from .views import ActivityView, OverviewView

app_name = "obs_center"

urlpatterns = [
    path("obs/overview/", OverviewView.as_view(), name="overview"),
    path("obs/activity/", ActivityView.as_view(), name="activity"),
]
