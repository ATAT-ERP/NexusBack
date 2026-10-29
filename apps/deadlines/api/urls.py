from django.urls import path

from apps.deadlines.api.views import DeadlineDetailView, DeadlineListView


urlpatterns = [
    path("deadlines/", DeadlineListView.as_view(), name="deadline-list"),
    path("deadlines/<uuid:id>/", DeadlineDetailView.as_view(), name="deadline-detail"),
]
