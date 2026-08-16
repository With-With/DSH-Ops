from django.urls import path

from .views import DraftApproveView, DraftListView, DraftRejectView

app_name = "reviews"

urlpatterns = [
    path("reviews/drafts/", DraftListView.as_view(), name="draft-list"),
    path("reviews/drafts/<int:pk>/approve/", DraftApproveView.as_view(), name="draft-approve"),
    path("reviews/drafts/<int:pk>/reject/", DraftRejectView.as_view(), name="draft-reject"),
]
