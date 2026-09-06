"""URL surface for the server-rendered Privacy Compliance Hub."""

from django.contrib.auth import views as auth_views
from django.urls import path

from .forms import VietnameseAuthenticationForm
from . import views


app_name = "privacy"

urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("", views.landing, name="landing"),
    path(
        "dang-nhap/",
        auth_views.LoginView.as_view(
            template_name="privacy/login.html",
            authentication_form=VietnameseAuthenticationForm,
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("dang-xuat/", views.logout_view, name="logout"),
    path("bao-mat/totp/", views.totp_setup, name="totp_setup"),
    path("bao-mat/totp/xac-thuc/", views.totp_verify, name="totp_verify"),
    path("doi-to-chuc/", views.switch_organization, name="switch_organization"),
    path("bang-dieu-khien/", views.dashboard, name="dashboard"),
    path("dong-y/", views.consent_center, name="consent_center"),
    path("dong-y/<int:event_id>/rut-lai/", views.withdraw_consent, name="withdraw_consent"),
    path("yeu-cau-du-lieu/", views.dsar_list, name="dsar_list"),
    path("yeu-cau-du-lieu/tao/", views.dsar_create, name="dsar_create"),
    path("yeu-cau-du-lieu/<str:reference>/", views.dsar_detail, name="dsar_detail"),
    path("yeu-cau-du-lieu/<str:reference>/phe-duyet/", views.approve_case, name="approve_case"),
    path("yeu-cau-du-lieu/<str:reference>/xuat/<str:format_name>/tao/", views.request_export, name="request_export"),
    path("xuat-du-lieu/<uuid:token>/phe-duyet/", views.approve_export, name="approve_export"),
    path("tuan-thu/", views.compliance_dashboard, name="compliance_dashboard"),
    path("tuan-thu/su-co/<int:incident_id>/phe-duyet/", views.approve_incident, name="approve_incident"),
    path("xuat-du-lieu/<str:token>/xac-thuc-lai/", views.export_reauthenticate, name="export_reauthenticate"),
    path("xuat-du-lieu/<str:token>/tai/", views.export_download, name="export_download"),
    path("doi-chieu-phap-ly/", views.legal_crosswalk, name="legal_crosswalk"),
]
