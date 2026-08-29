from django.urls import path

from apps.company.api.views import CompanyCreateView, CompanySearchView


urlpatterns = [
    path("companies/", CompanyCreateView.as_view(), name="company-create"),
    path("companies/search/", CompanySearchView.as_view(), name="company-search"),
]
