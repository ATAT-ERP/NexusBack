from django.urls import path

from apps.company.api.views import CompanyListView, CompanySearchView


urlpatterns = [
    path("companies/", CompanyListView.as_view(), name="company-list"),
    path("companies/search/", CompanySearchView.as_view(), name="company-search"),
]
