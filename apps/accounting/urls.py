from django.urls import path

from apps.accounting.views import (
    AccountDetailView,
    AccountListCreateView,
    DailyJournalView,
    GeneralLedgerView,
    JournalEntryDetailView,
    JournalEntryListView,
    JournalEntryPublishView,
    JournalEntryReverseView,
    TrialBalanceView,
)


urlpatterns = [
    path(
        "companies/<uuid:company_id>/journal-entries/<int:pk>/publish/",
        JournalEntryPublishView.as_view(),
        name="journal-entry-publish",
    ),
    path(
        "companies/<uuid:company_id>/journal-entries/<int:pk>/reverse/",
        JournalEntryReverseView.as_view(),
        name="journal-entry-reverse",
    ),
    path(
        "companies/<uuid:company_id>/journal-entries/",
        JournalEntryListView.as_view(),
        name="journal-entry-list",
    ),
    path(
        "companies/<uuid:company_id>/journal-entries/<int:pk>/",
        JournalEntryDetailView.as_view(),
        name="journal-entry-detail",
    ),
    path(
        "companies/<uuid:company_id>/reports/daily-journal/",
        DailyJournalView.as_view(),
        name="daily-journal",
    ),
    path(
        "companies/<uuid:company_id>/reports/general-ledger/<int:account_id>/",
        GeneralLedgerView.as_view(),
        name="general-ledger",
    ),
    path(
        "companies/<uuid:company_id>/reports/trial-balance/",
        TrialBalanceView.as_view(),
        name="trial-balance",
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
