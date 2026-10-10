from django.urls import path

from apps.company.api.views import (
    CompanyDetailView,
    CompanyListView,
    CompanyMemberDetailView,
    CompanyMembersView,
    CompanySearchView,
)


urlpatterns = [
    path("companies/", CompanyListView.as_view(), name="company-list"),
    path("companies/search/", CompanySearchView.as_view(), name="company-search"),
    path(
        "companies/<uuid:id>/members/",
        CompanyMembersView.as_view(),
        name="company-members",
    ),
    path(
        "companies/<uuid:id>/members/<uuid:user_id>/",
        CompanyMemberDetailView.as_view(),
        name="company-member-detail",
    ),
    path("companies/<uuid:id>/", CompanyDetailView.as_view(), name="company-detail"),
]
