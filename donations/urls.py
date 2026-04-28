from django.urls import path


from . import views
from .site_select_form import SiteSelectForm

urlpatterns = [
        path("donations/<int:pk>/detail/", views.donation_detail, name="donation-detail"),
    path("", views.home, name="home"),
    path("select-site/", views.site_select, name="site-select"),
    path("donations/new/", views.donation_create, name="donation-create"),
        path("donations/log/", views.donation_log, name="donation-log"),
        path("donations/<int:pk>/preview/", views.donation_preview_modal, name="donation-preview-modal"),
    path("api/donor-suggestions/", views.donor_suggestions, name="donor-suggestions"),
    path("api/donor-autocomplete/", views.donor_autocomplete, name="donor-autocomplete"),
    path("donations/export/csv/", views.donation_export_csv, name="donation-export-csv"),
    path("donations/export/pdf/", views.donation_export_pdf, name="donation-export-pdf"),
    path("donations/<int:pk>/edit/", views.donation_edit, name="donation-edit"),
    path("donations/<int:pk>/delete/", views.donation_delete, name="donation-delete"),
    path("unsubscribe/<str:token>/", views.unsubscribe, name="unsubscribe"),
]
