"""Server-rendered views for the Privacy Compliance Hub demo.

This module intentionally keeps policy decisions in the domain/service layer.
Views scope every tenant record to the active organization, expose simple role
guards, and present a Vietnamese-first workflow for the seminar prototype.
"""

from __future__ import annotations

import inspect
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection
from django.http import FileResponse, Http404, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST
from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice

from .forms import (
    ConsentSelectionForm,
    DSARCreateForm,
    OfficerApprovalForm,
    TOTPTokenForm,
)
from .tenant_context import set_current_organization


COMPLIANCE_ROLES = {
    "case_agent",
    "privacy_officer",
    "tenant_admin",
    "platform_auditor",
}
OFFICER_ROLES = {"privacy_officer"}
EXPORT_FORMATS = {"docx", "pdf"}


def _model(name):
    """Look up an optional domain model without making URL import fragile."""
    try:
        return apps.get_model("privacy", name)
    except LookupError:
        return None


def _has_field(model, name):
    if model is None:
        return False
    try:
        model._meta.get_field(name)
    except Exception:
        return False
    return True


def _manager(model, *, unrestricted=False):
    """Use the explicit unrestricted manager only for a user's memberships."""
    if model is None:
        return None
    if unrestricted and hasattr(model, "all_objects"):
        return model.all_objects
    return model.objects


def _empty_queryset(model):
    manager = _manager(model)
    return manager.none() if manager is not None else ()


def _tenant_queryset(model, organization):
    """Return a queryset that is tenant scoped both explicitly and by manager."""
    if model is None or organization is None:
        return _empty_queryset(model)
    queryset = _manager(model).all()
    if _has_field(model, "organization"):
        return queryset.filter(organization=organization)
    if _has_field(model, "organization_id"):
        return queryset.filter(organization_id=organization.pk)
    # Global/legal-reference models may have no organization field.
    return queryset


def _ordered(queryset, *fields):
    """Order when fields are available, otherwise leave a defensive queryset."""
    model = getattr(queryset, "model", None)
    usable = [field for field in fields if _has_field(model, field.lstrip("-"))]
    return queryset.order_by(*usable) if usable else queryset


def _safe_count(queryset):
    try:
        return queryset.count()
    except Exception:
        return 0


def _memberships_for(request):
    membership_model = _model("Membership")
    if membership_model is None or not request.user.is_authenticated:
        return []
    queryset = _manager(membership_model, unrestricted=True).filter(user=request.user)
    if _has_field(membership_model, "status"):
        queryset = queryset.filter(status="active")
    if _has_field(membership_model, "organization"):
        queryset = queryset.select_related("organization")
    try:
        return list(_ordered(queryset, "organization__name"))
    except Exception:
        return []


def _active_organization(request):
    """Resolve and validate the session's active organization for this user."""
    memberships = _memberships_for(request)
    if not memberships:
        return None

    requested_id = str(request.session.get("active_organization_id") or "")
    selected = next(
        (
            membership
            for membership in memberships
            if str(getattr(membership, "organization_id", "")) == requested_id
        ),
        None,
    )
    selected = selected or memberships[0]
    organization = getattr(selected, "organization", None)
    if organization is None:
        organization_model = _model("Organization")
        manager = _manager(organization_model, unrestricted=True)
        if manager is not None:
            organization = manager.filter(pk=getattr(selected, "organization_id", None)).first()
    if organization is None:
        return None

    if requested_id != str(organization.pk):
        request.session["active_organization_id"] = str(organization.pk)
    request.organization_id = str(organization.pk)
    request.active_organization = organization
    set_current_organization(str(organization.pk))
    return organization


def _membership_for(request, organization):
    organization_id = str(getattr(organization, "pk", ""))
    return next(
        (
            membership
            for membership in _memberships_for(request)
            if str(getattr(membership, "organization_id", "")) == organization_id
        ),
        None,
    )


def _role_names(request, organization):
    if getattr(request.user, "is_superuser", False):
        return {"tenant_admin", "privacy_officer", "platform_auditor"}
    membership = _membership_for(request, organization)
    if membership is None:
        return set()
    role = str(getattr(membership, "role", "")).strip().lower()
    roles = {role} if role else set()
    assignment_model = _model("RoleAssignment")
    if assignment_model is not None:
        assignments = _tenant_queryset(assignment_model, organization).filter(membership=membership)
        if _has_field(assignment_model, "scope"):
            assignments = assignments.filter(scope="organization")
        roles.update(str(value).strip().lower() for value in assignments.values_list("role", flat=True) if value)
    return roles


def _can_manage_compliance(request, organization):
    return bool(_role_names(request, organization) & COMPLIANCE_ROLES)


def _is_officer(request, organization):
    return bool(_role_names(request, organization) & OFFICER_ROLES)


def _totp_verified(request) -> bool:
    verifier = getattr(request.user, "is_verified", None)
    return bool(request.user.is_authenticated and callable(verifier) and verifier())


def _has_privileged_membership(request) -> bool:
    return any(
        str(getattr(membership, "role", "")).strip().lower() in COMPLIANCE_ROLES
        for membership in _memberships_for(request)
    )


def _totp_destination(request) -> str:
    has_confirmed_device = TOTPDevice.objects.filter(user=request.user, confirmed=True).exists()
    return reverse("privacy:totp_verify" if has_confirmed_device else "privacy:totp_setup")


def active_organization_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        organization = _active_organization(request)
        if organization is None:
            messages.error(request, "Tài khoản này chưa được cấp quyền vào tổ chức nào.")
            return redirect("privacy:landing")
        return view(request, *args, **kwargs)

    return wrapped


def compliance_required(view):
    @wraps(view)
    @login_required
    @active_organization_required
    def wrapped(request, *args, **kwargs):
        if not _can_manage_compliance(request, request.active_organization):
            raise PermissionDenied("Bạn không có quyền truy cập không gian tuân thủ của tổ chức này.")
        if not _totp_verified(request):
            messages.warning(request, "Vai trò đặc quyền cần xác thực TOTP trước khi vào không gian tuân thủ.")
            return redirect(_totp_destination(request))
        return view(request, *args, **kwargs)

    return wrapped


def _call_service(name, **kwargs):
    """Call an optional service using only the arguments it declares.

    Keeping this adapter here allows the portal to stay usable when a narrowly
    scoped service has a slightly smaller signature than the demo's full one.
    Exceptions raised *inside* a matched service are intentionally propagated.
    """
    try:
        from . import services

        function = getattr(services, name, None)
    except (ImportError, AttributeError):
        function = None
    if function is None:
        return False, None

    signature = inspect.signature(function)
    parameters = signature.parameters
    accepts_kwargs = any(parameter.kind == parameter.VAR_KEYWORD for parameter in parameters.values())
    call_kwargs = kwargs if accepts_kwargs else {key: value for key, value in kwargs.items() if key in parameters}
    return True, function(**call_kwargs)


def _subject_email(request):
    return (getattr(request.user, "email", "") or getattr(request.user, "username", "")).strip().lower()


def _case_request_choices():
    case_model = _model("DSARCase")
    if _has_field(case_model, "request_type"):
        choices = getattr(case_model._meta.get_field("request_type"), "choices", ())
        if choices:
            return choices
    return None


def _set_if_field(model, values, field_name, value):
    if _has_field(model, field_name):
        values[field_name] = value


def _display_value(instance, field_name, default="—"):
    value = getattr(instance, field_name, None)
    if value in (None, ""):
        return default
    display_method = getattr(instance, f"get_{field_name}_display", None)
    return display_method() if callable(display_method) else value


def _page_context(request, context=None):
    """Add navigation data without widening the global context processor."""
    context = dict(context or {})
    if request.user.is_authenticated:
        organization = context.get("organization") or getattr(request, "active_organization", None)
        context.setdefault("active_organization", organization)
        context.setdefault("available_organizations", _memberships_for(request))
        if organization is not None:
            context.setdefault("role_names", _role_names(request, organization))
            context.setdefault("can_manage_compliance", _can_manage_compliance(request, organization))
            context.setdefault("totp_required", _can_manage_compliance(request, organization))
            context.setdefault("totp_verified", _totp_verified(request))
    return context


@require_GET
def landing(request):
    """Public, deliberately modest entry page for the local-only demo."""
    return render(request, "privacy/landing.html", _page_context(request, {"page_title": "Privacy Compliance Hub"}))


@require_GET
def healthz(request):
    """Small unauthenticated liveness/readiness check without tenant data."""

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "Bạn đã đăng xuất khỏi Privacy Compliance Hub.")
    return redirect("privacy:landing")


@login_required
def totp_setup(request):
    """Enroll a privileged local account in TOTP without a third-party IdP."""

    if not _has_privileged_membership(request):
        raise PermissionDenied("TOTP chỉ được cấu hình cho tài khoản có vai trò đặc quyền trong prototype này.")
    if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
        return redirect("privacy:totp_verify")
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).order_by("pk").first()
    if device is None:
        device = TOTPDevice.objects.create(user=request.user, name="Privacy Compliance Hub", confirmed=False)
    form = TOTPTokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if device.verify_token(form.cleaned_data["token"]):
            device.confirmed = True
            device.save(update_fields=["confirmed"])
            otp_login(request, device)
            messages.success(request, "Đã kích hoạt TOTP cho tài khoản đặc quyền.")
            return redirect("privacy:dashboard")
        messages.error(request, "Mã TOTP không hợp lệ hoặc đã hết hạn. Hãy thử mã mới.")
    response = render(
        request,
        "privacy/totp_setup.html",
        _page_context(
            request,
            {
                "page_title": "Thiết lập TOTP",
                "form": form,
                "device": device,
                "config_url": device.config_url,
            },
        ),
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required
def totp_verify(request):
    """Re-establish an OTP-verified session for a privileged workflow."""

    if not _has_privileged_membership(request):
        raise PermissionDenied("TOTP chỉ được dùng cho tài khoản đặc quyền trong prototype này.")
    device = TOTPDevice.objects.filter(user=request.user, confirmed=True).order_by("pk").first()
    if device is None:
        return redirect("privacy:totp_setup")
    form = TOTPTokenForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if device.verify_token(form.cleaned_data["token"]):
            otp_login(request, device)
            messages.success(request, "Xác thực TOTP thành công.")
            return redirect("privacy:dashboard")
        messages.error(request, "Mã TOTP không hợp lệ hoặc đã hết hạn. Hãy thử mã mới.")
    response = render(
        request,
        "privacy/totp_verify.html",
        _page_context(request, {"page_title": "Xác thực TOTP", "form": form}),
    )
    response["Cache-Control"] = "no-store"
    return response


@login_required
@require_POST
def switch_organization(request):
    """Switch only to an organization for which the user has a membership."""
    organization_id = str(request.POST.get("organization_id") or "")
    membership = next(
        (
            item
            for item in _memberships_for(request)
            if str(getattr(item, "organization_id", "")) == organization_id
        ),
        None,
    )
    if membership is None:
        raise PermissionDenied("Bạn không có quyền chọn tổ chức này.")
    request.session["active_organization_id"] = organization_id
    set_current_organization(organization_id)
    messages.success(request, f"Đã chuyển sang tổ chức {getattr(membership.organization, 'name', '')}.")
    destination = request.POST.get("next") or reverse("privacy:dashboard")
    if not url_has_allowed_host_and_scheme(destination, {request.get_host()}, request.is_secure()):
        destination = reverse("privacy:dashboard")
    return redirect(destination)


@login_required
@active_organization_required
def dashboard(request):
    organization = request.active_organization
    subject_email = _subject_email(request)
    case_model = _model("DSARCase")
    consent_model = _model("ConsentEvent")
    incident_model = _model("Incident")
    activity_model = _model("ProcessingActivity")

    cases = _tenant_queryset(case_model, organization)
    if _has_field(case_model, "subject_email") and not _can_manage_compliance(request, organization):
        cases = cases.filter(subject_email__iexact=subject_email)
    consents = _tenant_queryset(consent_model, organization)
    if _has_field(consent_model, "subject_email"):
        consents = consents.filter(subject_email__iexact=subject_email)
    if _has_field(consent_model, "status"):
        consents = consents.filter(status="granted")

    context = {
        "page_title": "Bảng điều khiển",
        "organization": organization,
        "membership": _membership_for(request, organization),
        "role_names": _role_names(request, organization),
        "can_manage_compliance": _can_manage_compliance(request, organization),
        "open_case_count": _safe_count(cases.exclude(status__in=["completed", "closed", "rejected", "cancelled"])) if _has_field(case_model, "status") else _safe_count(cases),
        "active_consent_count": _safe_count(consents),
        "incident_count": _safe_count(_tenant_queryset(incident_model, organization)),
        "activity_count": _safe_count(_tenant_queryset(activity_model, organization)),
        "recent_cases": _ordered(cases, "-submitted_at", "-pk")[:5],
        "recent_incidents": _ordered(_tenant_queryset(incident_model, organization), "-detected_at", "-pk")[:5],
    }
    return render(request, "privacy/dashboard.html", _page_context(request, context))


@login_required
@active_organization_required
def consent_center(request):
    organization = request.active_organization
    purpose_model = _model("ProcessingPurpose")
    notice_model = _model("NoticeVersion")
    consent_model = _model("ConsentEvent")
    purposes = _tenant_queryset(purpose_model, organization)
    if _has_field(purpose_model, "active"):
        purposes = purposes.filter(active=True)
    purposes = _ordered(purposes, "name", "pk")

    notices = _tenant_queryset(notice_model, organization)
    if _has_field(notice_model, "status"):
        notices = notices.filter(status__in=["published", "active"])
    notice = _ordered(notices, "-effective_at", "-pk").first()
    if notice is None:
        messages.warning(request, "Tổ chức chưa công bố phiên bản thông báo xử lý dữ liệu để ghi nhận consent.")

    form = ConsentSelectionForm(request.POST or None, purposes=purposes)
    if request.method == "POST":
        if notice is None:
            form.add_error(None, "Không thể ghi nhận consent khi chưa có thông báo xử lý dữ liệu đang hiệu lực.")
        if form.is_valid():
            subject_email = _subject_email(request)
            saved = 0
            for purpose in form.selected_purposes():
                called, result = _call_service(
                    "record_consent",
                    organization=organization,
                    subject_email=subject_email,
                    purpose=purpose,
                    notice_version=notice,
                    actor=request.user,
                    subject_user=request.user,
                    evidence={"channel": "portal", "notice_version": getattr(notice, "version", "")},
                )
                if not called:
                    values = {}
                    _set_if_field(consent_model, values, "organization", organization)
                    _set_if_field(consent_model, values, "subject_email", subject_email)
                    _set_if_field(consent_model, values, "purpose", purpose)
                    _set_if_field(consent_model, values, "notice_version", notice)
                    _set_if_field(consent_model, values, "status", "granted")
                    _set_if_field(consent_model, values, "occurred_at", timezone.now())
                    _manager(consent_model).create(**values)
                saved += 1
            messages.success(request, f"Đã ghi nhận {saved} lựa chọn consent riêng theo từng mục đích.")
            return redirect("privacy:consent_center")

    events = _tenant_queryset(consent_model, organization)
    if _has_field(consent_model, "subject_email"):
        events = events.filter(subject_email__iexact=_subject_email(request))
    event_rows = list(_ordered(events, "-occurred_at", "-pk"))
    current_purpose_ids = set()
    for event in event_rows:
        purpose_id = getattr(event, "purpose_id", None)
        event.is_current = purpose_id not in current_purpose_ids
        event.can_withdraw = bool(event.is_current and getattr(event, "status", "") == "granted")
        current_purpose_ids.add(purpose_id)
    context = {
        "page_title": "Trung tâm đồng ý",
        "organization": organization,
        "form": form,
        "notice": notice,
        "purposes": purposes,
        "consent_events": event_rows,
    }
    return render(request, "privacy/consent_center.html", _page_context(request, context))


@login_required
@active_organization_required
@require_POST
def withdraw_consent(request, event_id):
    organization = request.active_organization
    consent_model = _model("ConsentEvent")
    events = _tenant_queryset(consent_model, organization)
    if _has_field(consent_model, "subject_email") and not _can_manage_compliance(request, organization):
        events = events.filter(subject_email__iexact=_subject_email(request))
    event = get_object_or_404(events, pk=event_id)
    if getattr(event, "status", "") != "granted":
        messages.info(request, "Sự kiện consent này không còn ở trạng thái đang hiệu lực.")
        return redirect("privacy:consent_center")

    called, _ = _call_service("withdraw_consent", event=event, actor=request.user)
    if not called:
        event.status = "withdrawn"
        if _has_field(consent_model, "occurred_at"):
            event.occurred_at = timezone.now()
        event.save(update_fields=[field for field in ("status", "occurred_at") if _has_field(consent_model, field)])
    messages.success(request, "Đã ghi nhận yêu cầu rút lại sự đồng ý. Việc ngừng xử lý sẽ được theo dõi trong hồ sơ tuân thủ.")
    return redirect("privacy:consent_center")


@login_required
@active_organization_required
def dsar_list(request):
    organization = request.active_organization
    case_model = _model("DSARCase")
    cases = _tenant_queryset(case_model, organization)
    can_manage = _can_manage_compliance(request, organization)
    if _has_field(case_model, "subject_email") and not can_manage:
        cases = cases.filter(subject_email__iexact=_subject_email(request))
    return render(
        request,
        "privacy/dsar_list.html",
        _page_context(request, {
            "page_title": "Yêu cầu quyền dữ liệu",
            "organization": organization,
            "cases": _ordered(cases, "-submitted_at", "-pk"),
            "can_manage_compliance": can_manage,
        }),
    )


@login_required
@active_organization_required
def dsar_create(request):
    organization = request.active_organization
    form = DSARCreateForm(
        request.POST or None,
        initial={"subject_email": _subject_email(request)},
        request_type_choices=_case_request_choices(),
    )
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        called, case = _call_service(
            "create_dsar_case",
            organization=organization,
            subject_email=data["subject_email"].lower(),
            request_type=data["request_type"],
            description=data.get("details", ""),
            subject_user=request.user,
            actor=request.user,
        )
        if not called:
            case_model = _model("DSARCase")
            values = {}
            _set_if_field(case_model, values, "organization", organization)
            _set_if_field(case_model, values, "subject_email", data["subject_email"].lower())
            _set_if_field(case_model, values, "request_type", data["request_type"])
            _set_if_field(case_model, values, "reference", f"DSAR-{uuid4().hex[:10].upper()}")
            _set_if_field(case_model, values, "status", "submitted")
            _set_if_field(case_model, values, "submitted_at", timezone.now())
            _set_if_field(case_model, values, "requires_officer_approval", data["request_type"] in {"erasure", "portability"})
            case = _manager(case_model).create(**values)
        messages.success(request, "Yêu cầu đã được tạo. Hệ thống dùng quy tắc pháp lý có phiên bản để theo dõi thời hạn.")
        return redirect("privacy:dsar_detail", reference=case.reference)
    return render(
        request,
        "privacy/dsar_form.html",
        _page_context(request, {"page_title": "Tạo yêu cầu quyền dữ liệu", "organization": organization, "form": form}),
    )


def _case_for_request(request, organization, reference):
    case_model = _model("DSARCase")
    cases = _tenant_queryset(case_model, organization)
    case = get_object_or_404(cases, reference=reference)
    if not _can_manage_compliance(request, organization) and getattr(case, "subject_email", "").lower() != _subject_email(request):
        raise PermissionDenied("Bạn chỉ có thể xem yêu cầu dữ liệu của chính mình.")
    return case


@login_required
@active_organization_required
def dsar_detail(request, reference):
    organization = request.active_organization
    case = _case_for_request(request, organization, reference)
    artifact_model = _model("ExportArtifact")
    artifacts = _tenant_queryset(artifact_model, organization)
    if _has_field(artifact_model, "case"):
        artifacts = artifacts.filter(case=case)
    else:
        artifacts = _empty_queryset(artifact_model)
    context = {
        "page_title": f"Yêu cầu {getattr(case, 'reference', '')}",
        "organization": organization,
        "case": case,
        "artifacts": _ordered(artifacts, "-expires_at", "-pk"),
        "can_approve": _is_officer(request, organization) and _totp_verified(request) and bool(getattr(case, "requires_officer_approval", False)),
        "can_approve_export": _is_officer(request, organization) and _totp_verified(request),
        "approval_form": OfficerApprovalForm(),
        "can_manage_compliance": _can_manage_compliance(request, organization),
        "can_request_export": getattr(case, "status", "") in {"approved", "completed"},
    }
    return render(request, "privacy/dsar_detail.html", _page_context(request, context))


@login_required
@active_organization_required
@require_POST
def approve_case(request, reference):
    organization = request.active_organization
    if not _is_officer(request, organization):
        raise PermissionDenied("Chỉ Privacy Officer được phê duyệt hồ sơ này.")
    if not _totp_verified(request):
        messages.warning(request, "Privacy Officer phải xác thực TOTP trước khi phê duyệt.")
        return redirect(_totp_destination(request))
    case = _case_for_request(request, organization, reference)
    form = OfficerApprovalForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Cần xác nhận rằng bạn đã rà soát hồ sơ trước khi phê duyệt.")
        return redirect("privacy:dsar_detail", reference=reference)
    called, _ = _call_service("approve_case", case=case, officer=request.user, actor=request.user)
    if not called and _has_field(case.__class__, "status"):
        case.status = "approved"
        case.save(update_fields=["status"])
    messages.success(request, "Privacy Officer đã ghi nhận quyết định phê duyệt trong audit trail.")
    return redirect("privacy:dsar_detail", reference=reference)


@login_required
@active_organization_required
@require_POST
def request_export(request, reference, format_name):
    """Let a subject request an educational export; an officer must release it."""

    organization = request.active_organization
    if format_name not in EXPORT_FORMATS:
        raise Http404("Định dạng xuất không được hỗ trợ.")
    case = _case_for_request(request, organization, reference)
    artifact_model = _model("ExportArtifact")
    pending = _tenant_queryset(artifact_model, organization).filter(
        case=case, format=format_name, status__in=["pending_approval", "approved", "generating"]
    ).order_by("-created_at").first()
    if pending is not None:
        messages.info(request, "Đã có yêu cầu xuất cùng định dạng đang chờ hoặc đang tạo.")
        return redirect("privacy:dsar_detail", reference=reference)
    try:
        called, _ = _call_service("create_export_artifact", case=case, format=format_name, actor=request.user)
        if not called:
            raise ValidationError("Dịch vụ xuất dữ liệu chưa sẵn sàng.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "Đã tạo yêu cầu xuất. Privacy Officer phải phê duyệt trước khi có tệp tải.")
    return redirect("privacy:dsar_detail", reference=reference)


@login_required
@active_organization_required
@require_POST
def approve_export(request, token):
    """Approve and render a local draft only after explicit officer review."""

    organization = request.active_organization
    if not _is_officer(request, organization):
        raise PermissionDenied("Chỉ Privacy Officer được phê duyệt bản xuất.")
    if not _totp_verified(request):
        messages.warning(request, "Privacy Officer phải xác thực TOTP trước khi phê duyệt bản xuất.")
        return redirect(_totp_destination(request))
    artifact_model = _model("ExportArtifact")
    artifact = get_object_or_404(_tenant_queryset(artifact_model, organization), download_token=token)
    form = OfficerApprovalForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Cần xác nhận việc rà soát trước khi phê duyệt bản xuất.")
        return redirect("privacy:dsar_detail", reference=artifact.case.reference)
    try:
        called, artifact = _call_service("approve_export_artifact", artifact=artifact, officer=request.user, actor=request.user)
        if not called:
            raise ValidationError("Dịch vụ phê duyệt xuất chưa sẵn sàng.")
        called, _ = _call_service("generate_export_artifact", artifact=artifact, actor=request.user)
        if not called:
            raise ValidationError("Dịch vụ tạo tệp xuất chưa sẵn sàng.")
    except (ValidationError, PermissionDenied) as exc:
        messages.error(request, "; ".join(exc.messages) if hasattr(exc, "messages") else str(exc))
    else:
        messages.success(request, "Đã phê duyệt và tạo bản nháp học tập cục bộ. Liên kết tải yêu cầu xác thực lại.")
    return redirect("privacy:dsar_detail", reference=artifact.case.reference)


@compliance_required
def compliance_dashboard(request):
    organization = request.active_organization
    models = {
        "activities": _model("ProcessingActivity"),
        "vendors": _model("Vendor"),
        "transfers": _model("Transfer"),
        "dossiers": _model("ImpactDossier"),
        "incidents": _model("Incident"),
    }
    querysets = {name: _tenant_queryset(model, organization) for name, model in models.items()}
    audit_status = None
    try:
        called, audit_status = _call_service("verify_audit_chain", organization=organization)
        if not called:
            audit_status = None
    except Exception:
        # A dashboard must not expose implementation details from an audit check.
        audit_status = False

    return render(
        request,
        "privacy/compliance_dashboard.html",
        _page_context(request, {
            "page_title": "Không gian tuân thủ",
            "organization": organization,
            "activity_count": _safe_count(querysets["activities"]),
            "vendor_count": _safe_count(querysets["vendors"]),
            "transfer_count": _safe_count(querysets["transfers"]),
            "dossier_count": _safe_count(querysets["dossiers"]),
            "incident_count": _safe_count(querysets["incidents"]),
            "activities": _ordered(querysets["activities"], "name", "pk")[:8],
            "vendors": _ordered(querysets["vendors"], "name", "pk")[:8],
            "transfers": _ordered(querysets["transfers"], "destination_country", "pk")[:8],
            "dossiers": _ordered(querysets["dossiers"], "title", "pk")[:8],
            "incidents": _ordered(querysets["incidents"], "-detected_at", "-pk")[:8],
            "can_approve": _is_officer(request, organization) and _totp_verified(request),
            "approval_form": OfficerApprovalForm(),
            "audit_status": audit_status,
        }),
    )


@login_required
@active_organization_required
@require_POST
def approve_incident(request, incident_id):
    organization = request.active_organization
    if not _is_officer(request, organization):
        raise PermissionDenied("Chỉ Privacy Officer được phê duyệt hồ sơ sự cố.")
    if not _totp_verified(request):
        messages.warning(request, "Privacy Officer phải xác thực TOTP trước khi phê duyệt sự cố.")
        return redirect(_totp_destination(request))
    incident_model = _model("Incident")
    incident = get_object_or_404(_tenant_queryset(incident_model, organization), pk=incident_id)
    form = OfficerApprovalForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Cần xác nhận việc rà soát trước khi phê duyệt sự cố.")
        return redirect("privacy:compliance_dashboard")
    called, _ = _call_service("approve_workflow_item", item=incident, officer=request.user, actor=request.user)
    if not called and _has_field(incident_model, "status"):
        incident.status = "approved"
        incident.save(update_fields=["status"])
    messages.success(request, "Đã ghi nhận phê duyệt sự cố trong audit trail.")
    return redirect("privacy:compliance_dashboard")


def _can_access_case(request, case, organization):
    return _can_manage_compliance(request, organization) or getattr(case, "subject_email", "").lower() == _subject_email(request)


@login_required
@active_organization_required
def export_reauthenticate(request, token):
    """Confirm the current user's password before releasing a generated export."""
    artifact_model = _model("ExportArtifact")
    artifact = get_object_or_404(_tenant_queryset(artifact_model, request.active_organization), download_token=token)
    case = getattr(artifact, "case", None)
    if case is None or not _can_access_case(request, case, request.active_organization):
        raise PermissionDenied("Bạn không có quyền tải tệp xuất này.")
    if request.method == "POST":
        password = request.POST.get("password", "")
        if request.user.check_password(password):
            request.session["privacy_reauthenticated_at"] = timezone.now().isoformat()
            return redirect("privacy:export_download", token=token)
        messages.error(request, "Mật khẩu không đúng.")
    return render(
        request,
        "privacy/export_reauthenticate.html",
        _page_context(request, {"page_title": "Xác thực lại để tải dữ liệu", "artifact": artifact, "organization": request.active_organization}),
    )


def _recently_reauthenticated(request):
    raw_time = request.session.get("privacy_reauthenticated_at")
    if not raw_time:
        return False
    try:
        verified_at = datetime.fromisoformat(raw_time)
        if timezone.is_naive(verified_at):
            verified_at = timezone.make_aware(verified_at, timezone.get_current_timezone())
    except (TypeError, ValueError):
        return False
    return timezone.now() - verified_at <= timedelta(minutes=10)


@login_required
@active_organization_required
@require_GET
def export_download(request, token):
    organization = request.active_organization
    artifact_model = _model("ExportArtifact")
    artifact = get_object_or_404(_tenant_queryset(artifact_model, organization), download_token=token)
    case = getattr(artifact, "case", None)
    if case is None or not _can_access_case(request, case, organization):
        raise PermissionDenied("Bạn không có quyền tải tệp xuất này.")
    expires_at = getattr(artifact, "expires_at", None)
    if expires_at and expires_at <= timezone.now():
        messages.error(request, "Liên kết tải đã hết hạn. Hãy yêu cầu tạo lại bản xuất.")
        return redirect("privacy:dsar_detail", reference=case.reference)
    if not _recently_reauthenticated(request):
        return redirect("privacy:export_reauthenticate", token=token)
    if getattr(artifact, "status", "ready") not in {"ready", "completed", "available"}:
        messages.info(request, "Tệp xuất vẫn chưa sẵn sàng để tải.")
        return redirect("privacy:dsar_detail", reference=case.reference)

    filename = str(getattr(artifact, "file_name", "") or "")
    if not filename:
        raise Http404("Không tìm thấy tệp xuất.")
    export_root = Path(settings.EXPORT_ROOT).resolve()
    candidate = (export_root / filename).resolve()
    try:
        candidate.relative_to(export_root)
    except ValueError as exc:
        raise Http404("Tên tệp xuất không hợp lệ.") from exc
    if not candidate.is_file():
        raise Http404("Tệp xuất hiện chưa có trên máy chủ local.")
    return FileResponse(candidate.open("rb"), as_attachment=True, filename=candidate.name)


def legal_crosswalk(request):
    """Show current Vietnamese rules, historic NĐ 13 references, and GDPR scope."""
    organization = _active_organization(request) if request.user.is_authenticated else None
    rule_version_model = _model("RuleVersion")
    rule_versions = rule_version_model.objects.select_related("legal_rule").all() if rule_version_model else []
    static_rules = [
        {
            "framework": "Việt Nam hiện hành",
            "title": "Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15",
            "status": "Hiệu lực từ 01/01/2026",
            "scope": "Đồng ý, quyền của chủ thể, hồ sơ tác động, chuyển dữ liệu và sự cố.",
            "legal_review": True,
            "source_url": "https://vanban.chinhphu.vn/?classid=1&docid=214590&pageid=27160&typegroup=",
        },
        {
            "framework": "Việt Nam hiện hành",
            "title": "Nghị định 356/2025/NĐ-CP",
            "status": "Hiệu lực từ 01/01/2026",
            "scope": "Chi tiết hóa chứng cứ consent, quy trình DSAR, hồ sơ và điều kiện dịch vụ.",
            "legal_review": True,
            "source_url": "https://vanban.chinhphu.vn/default.aspx?docid=216387&pageid=27160",
        },
        {
            "framework": "Đối chiếu lịch sử",
            "title": "Nghị định 13/2023/NĐ-CP",
            "status": "Đã bị thay thế/bãi bỏ theo quy định hiện hành",
            "scope": "Chỉ dùng để đối chiếu học thuật; không gắn nhãn là chuẩn compliance hiện hành.",
            "legal_review": False,
        },
        {
            "framework": "GDPR",
            "title": "General Data Protection Regulation",
            "status": "Đánh giá theo điều kiện áp dụng thực tế",
            "scope": "Không được mặc định áp dụng cho mọi tổ chức hoặc mọi hoạt động xử lý.",
            "legal_review": True,
            "source_url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679",
        },
    ]
    return render(
        request,
        "privacy/legal_crosswalk.html",
        _page_context(request, {
            "page_title": "Đối chiếu khung pháp lý",
            "organization": organization,
            "static_rules": static_rules,
            "rule_versions": _ordered(rule_versions, "legal_rule__jurisdiction", "legal_rule__code", "pk") if hasattr(rule_versions, "order_by") else rule_versions,
        }),
    )
