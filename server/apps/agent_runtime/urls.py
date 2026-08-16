from django.urls import path

from .views import (
    AgentInvocationListView,
    ArtifactDraftDetailView,
    ArtifactDraftListView,
    GatewayTestView,
)

app_name = "agent_runtime"

urlpatterns = [
    path("agent/invocations/", AgentInvocationListView.as_view(), name="invocation-list"),
    path("agent/drafts/", ArtifactDraftListView.as_view(), name="draft-list"),
    path("agent/drafts/<int:pk>/", ArtifactDraftDetailView.as_view(), name="draft-detail"),
    path("agent/gateway/test/", GatewayTestView.as_view(), name="gateway-test"),
]
