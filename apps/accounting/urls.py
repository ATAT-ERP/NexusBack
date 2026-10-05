from django.urls import path

from apps.accounting.views import (
    AccountDetailView,
    AccountListCreateView,
    JournalEntryPublishView,
)


urlpatterns = [
    path(
        "companies/<uuid:company_id>/journal-entries/<int:pk>/publish/",
        JournalEntryPublishView.as_view(),
        name="journal-entry-publish",
    ),
    path(
        "companies/<uuid:company_id>/accounts/",
        AccountListCreateView.as_view(),
        name="account-list",
    ),
    path(
        "companies/<uuid:company_id>/accounts/<int:pk>/",
        AccountDetailView.as_view(),
        name="account-detail",
    ),
]
