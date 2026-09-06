"""Transaction-safe privacy workflow services.

Views deliberately call these functions instead of changing workflow state
directly.  Each write runs in an explicit tenant scope, which also sets the
PostgreSQL RLS setting for Celery and management-command code.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from typing import Any, Iterator

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    AuditEvent,
    ConsentEvent,
    DSARCase,
    ExemptionAssessment,
    ExportArtifact,
    ImpactDossier,
    Incident,
    LegalHold,
    LegalRule,
    Membership,
    NoticeVersion,
    Organization,
    ProcessingPurpose,
    RetentionPolicy,
    RoleAssignment,
    RuleVersion,
    Transfer,
    Vendor,
    AuditChainReport,
    verify_audit_chain as _verify_audit_chain,
)
from .tenant_context import get_current_organization_id, tenant_context


class WorkflowValidationError(ValidationError):
    """A validation error that callers may safely render to a user."""


def _organization(value: Organization | str) -> Organization:
    if isinstance(value, Organization):
        return value
    return Organization.objects.get(pk=value)


@contextmanager
def organization_scope(organization: Organization | str) -> Iterator[Organization]:
    """Establish a transaction-local tenant context, including PostgreSQL RLS."""

    resolved = _organization(organization)
    current = get_current_organization_id()
    if current and str(current) != str(resolved.pk):
        raise PermissionDenied("Không thể truy cập hoặc thay đổi dữ liệu của tổ chức khác.")

    with tenant_context(str(resolved.pk)), transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_organization_id', %s, true)",
                    [str(resolved.pk)],
                )
        yield resolved


def _get_tenant_instance(model, value, organization: Organization):
    if isinstance(value, model):
        if value.organization_id != organization.pk:
            raise PermissionDenied("Đối tượng không thuộc tổ chức đang hoạt động.")
        return value
    return model.objects.get(pk=value, organization=organization)


def _is_privacy_officer(organization: Organization, user) -> bool:
    if user is None:
        return False
    if Membership.objects.filter(
        organization=organization,
        user=user,
        role=Membership.Role.PRIVACY_OFFICER,
        status=Membership.Status.ACTIVE,
    ).exists():
        return True
    # An organization-wide delegated role is equivalent to the primary role.
    return RoleAssignment.all_objects.filter(
        organization=organization,
        membership__user=user,
        membership__status=Membership.Status.ACTIVE,
        role=Membership.Role.PRIVACY_OFFICER,
        scope=RoleAssignment.Scope.ORGANIZATION,
    ).exists()


def require_privacy_officer(organization: Organization, officer) -> None:
    if not _is_privacy_officer(organization, officer):
        raise PermissionDenied("Quyết định này cần Privacy Officer đang hoạt động phê duyệt.")


def audit(
    organization: Organization,
    event_type: str,
    *,
    actor=None,
    instance=None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    """Append a metadata-minimized audit event to the organization's ledger."""

    return AuditEvent.append(
        organization=organization,
        event_type=event_type,
        actor=actor,
        instance=instance,
        metadata=metadata or {},
    )


def resolve_rule_version(
    rule_code: str,
    *,
    when=None,
    jurisdiction: str | None = None,
) -> RuleVersion:
    """Choose a dated rule version rather than hard-coding a legal deadline."""

    when = when or timezone.localdate()
    versions = RuleVersion.objects.select_related("legal_rule").filter(
        legal_rule__code=rule_code,
        legal_rule__active=True,
        is_current=True,
        effective_from__lte=when,
    ).filter(Q(effective_until__isnull=True) | Q(effective_until__gte=when))
    if jurisdiction:
        versions = versions.filter(legal_rule__jurisdiction=jurisdiction)
    version = versions.order_by("-effective_from", "-pk").first()
    if version is None:
        raise WorkflowValidationError(
            f"Chưa cấu hình phiên bản quy tắc đang hiệu lực cho '{rule_code}'. "
            "Hãy nhờ Privacy Officer/legal review bổ sung rule catalog."
        )
    return version


def calculate_deadline(submitted_at, rule_version: RuleVersion):
    if rule_version.duration_days is None:
        raise WorkflowValidationError("Phiên bản quy tắc này chưa cấu hình thời hạn vận hành.")
    return submitted_at + timedelta(days=rule_version.duration_days)


def record_consent(
    *,
    organization: Organization | str,
    subject_email: str,
    purpose: ProcessingPurpose | int,
    notice_version: NoticeVersion | int,
    actor=None,
    subject_user=None,
    evidence: dict[str, Any] | None = None,
    evidence_reference: str = "",
) -> ConsentEvent:
    """Record an affirmative, purpose-specific consent event.

    No default consent is created anywhere in the model or service layer.
    """

    with organization_scope(organization) as organization:
        purpose = _get_tenant_instance(ProcessingPurpose, purpose, organization)
        notice_version = _get_tenant_instance(NoticeVersion, notice_version, organization)
        if not purpose.active:
            raise WorkflowValidationError("Không thể ghi nhận đồng ý cho mục đích đã ngừng áp dụng.")
        if not notice_version.is_effective:
            raise WorkflowValidationError("Thông báo xử lý dữ liệu chưa ở trạng thái công bố và còn hiệu lực.")
        event = ConsentEvent(
            organization=organization,
            subject_email=subject_email.strip().lower(),
            subject_user=subject_user,
            purpose=purpose,
            notice_version=notice_version,
            status=ConsentEvent.Status.GRANTED,
            actor=actor,
            evidence=evidence or {},
            evidence_reference=evidence_reference,
        )
        event.full_clean()
        event.save()
        audit(
            organization,
            "consent.granted",
            actor=actor,
            instance=event,
            metadata={"purpose": purpose.code, "notice_version": notice_version.version},
        )
        return event


def withdraw_consent(
    *,
    event: ConsentEvent | int | None = None,
    organization: Organization | str | None = None,
    subject_email: str | None = None,
    purpose: ProcessingPurpose | int | None = None,
    actor=None,
    reason: str = "",
) -> ConsentEvent:
    """Append a withdrawal event; never rewrite the original consent proof."""

    if isinstance(event, ConsentEvent):
        organization = event.organization
    if organization is None:
        raise WorkflowValidationError("Cần tổ chức hoặc sự kiện consent để rút lại đồng ý.")
    with organization_scope(organization) as organization:
        original = _get_tenant_instance(ConsentEvent, event, organization) if event is not None else None
        if original is not None:
            subject_email = original.subject_email
            purpose = original.purpose
            notice_version = original.notice_version
        else:
            if not subject_email or purpose is None:
                raise WorkflowValidationError("Cần email chủ thể và mục đích để rút consent.")
            purpose = _get_tenant_instance(ProcessingPurpose, purpose, organization)
            latest = ConsentEvent.current_for(organization, subject_email, purpose)
            if latest is None:
                raise WorkflowValidationError("Không có sự kiện consent trước đó để rút.")
            notice_version = latest.notice_version
        withdrawal = ConsentEvent(
            organization=organization,
            subject_email=subject_email.strip().lower(),
            purpose=purpose,
            notice_version=notice_version,
            status=ConsentEvent.Status.WITHDRAWN,
            actor=actor,
            evidence={"withdraws_event_id": original.pk if original is not None else None, "reason": reason},
        )
        withdrawal.full_clean()
        withdrawal.save()
        audit(
            organization,
            "consent.withdrawn",
            actor=actor,
            instance=withdrawal,
            metadata={"purpose": purpose.code},
        )
        return withdrawal


def consent_is_active(*, organization: Organization | str, subject_email: str, purpose: ProcessingPurpose | int) -> bool:
    with organization_scope(organization) as organization:
        purpose = _get_tenant_instance(ProcessingPurpose, purpose, organization)
        latest = ConsentEvent.current_for(organization, subject_email, purpose)
        return bool(latest and latest.status == ConsentEvent.Status.GRANTED)


def create_dsar_case(
    *,
    organization: Organization | str,
    subject_email: str,
    request_type: str,
    description: str = "",
    subject_user=None,
    actor=None,
    rule_version: RuleVersion | int | None = None,
    submitted_at=None,
    requires_officer_approval: bool = True,
) -> DSARCase:
    """Create a submitted DSAR with its deadline derived from a rule version."""

    with organization_scope(organization) as organization:
        submitted_at = submitted_at or timezone.now()
        if rule_version is None:
            # A tenant may publish specific, versioned rules for each DSAR
            # category.  The generic rule remains an explicit fallback for a
            # new request type until Privacy Officer/legal review configures
            # that category; no statutory deadline is hard-coded here.
            try:
                rule_version = resolve_rule_version(f"dsar-{request_type}", when=submitted_at.date())
            except WorkflowValidationError:
                rule_version = resolve_rule_version("dsar-response", when=submitted_at.date())
        elif not isinstance(rule_version, RuleVersion):
            rule_version = RuleVersion.objects.get(pk=rule_version)
        due_at = calculate_deadline(submitted_at, rule_version)
        case = DSARCase(
            organization=organization,
            subject_email=subject_email.strip().lower(),
            subject_user=subject_user,
            request_type=request_type,
            description=description,
            status=DSARCase.Status.SUBMITTED,
            sla_state=DSARCase.SlaState.ON_TRACK,
            rule_version=rule_version,
            submitted_at=submitted_at,
            due_at=due_at,
            requires_officer_approval=requires_officer_approval,
        )
        case.full_clean()
        case.save()
        audit(
            organization,
            "dsar.submitted",
            actor=actor,
            instance=case,
            metadata={"request_type": case.request_type, "rule_version": rule_version.version},
        )
        return case


def extend_dsar_deadline(*, case: DSARCase | int, new_due_at, reason: str, actor=None) -> DSARCase:
    organization = case.organization if isinstance(case, DSARCase) else None
    if organization is None:
        raise WorkflowValidationError("Dùng đối tượng DSAR đã được tenant-scope để gia hạn.")
    with organization_scope(organization) as organization:
        case = _get_tenant_instance(DSARCase, case, organization)
        case.extended_due_at = new_due_at
        case.extension_reason = reason.strip()
        case.extension_granted_at = timezone.now()
        case.sla_state = DSARCase.SlaState.EXTENDED
        case.full_clean()
        case.save()
        audit(organization, "dsar.deadline_extended", actor=actor, instance=case, metadata={"new_due_at": new_due_at.isoformat()})
        return case


def submit_case_for_officer_approval(*, case: DSARCase | int, actor=None) -> DSARCase:
    organization = case.organization if isinstance(case, DSARCase) else None
    if organization is None:
        raise WorkflowValidationError("Dùng đối tượng DSAR đã được tenant-scope để gửi phê duyệt.")
    with organization_scope(organization) as organization:
        case = _get_tenant_instance(DSARCase, case, organization)
        if case.status in {DSARCase.Status.COMPLETED, DSARCase.Status.CANCELLED, DSARCase.Status.REJECTED}:
            raise WorkflowValidationError("Không thể gửi lại hồ sơ đã kết thúc để phê duyệt.")
        case.status = DSARCase.Status.PENDING_OFFICER_APPROVAL
        case.full_clean()
        case.save()
        audit(organization, "dsar.approval_requested", actor=actor, instance=case)
        return case


def approve_case(*, case: DSARCase | int, officer, actor=None, decision_notes: str = "") -> DSARCase:
    organization = case.organization if isinstance(case, DSARCase) else None
    if organization is None:
        raise WorkflowValidationError("Dùng đối tượng DSAR đã được tenant-scope để phê duyệt.")
    with organization_scope(organization) as organization:
        require_privacy_officer(organization, officer)
        case = _get_tenant_instance(DSARCase, case, organization)
        if case.status in {DSARCase.Status.COMPLETED, DSARCase.Status.CANCELLED, DSARCase.Status.REJECTED}:
            raise WorkflowValidationError("Không thể phê duyệt hồ sơ đã kết thúc.")
        case.status = DSARCase.Status.APPROVED
        case.officer_approved_by = officer
        case.officer_approved_at = timezone.now()
        case.decision_notes = decision_notes.strip() or case.decision_notes
        case.full_clean()
        case.save()
        audit(organization, "dsar.approved", actor=actor or officer, instance=case)
        return case


def complete_case(*, case: DSARCase | int, actor=None, decision_notes: str = "") -> DSARCase:
    organization = case.organization if isinstance(case, DSARCase) else None
    if organization is None:
        raise WorkflowValidationError("Dùng đối tượng DSAR đã được tenant-scope để hoàn tất.")
    with organization_scope(organization) as organization:
        case = _get_tenant_instance(DSARCase, case, organization)
        if case.requires_officer_approval and not case.officer_approved_by_id:
            raise WorkflowValidationError("Hồ sơ cần Privacy Officer phê duyệt trước khi hoàn tất.")
        if case.request_type == DSARCase.RequestType.ERASURE and case.has_active_legal_hold:
            raise WorkflowValidationError("Không thể hoàn tất yêu cầu xóa khi còn legal hold hiệu lực.")
        case.status = DSARCase.Status.COMPLETED
        case.completed_at = timezone.now()
        case.decision_notes = decision_notes.strip() or case.decision_notes
        case.full_clean()
        case.save()
        audit(organization, "dsar.completed", actor=actor, instance=case)
        return case


def anonymize_case(*, case: DSARCase | int, actor=None) -> DSARCase:
    organization = case.organization if isinstance(case, DSARCase) else None
    if organization is None:
        raise WorkflowValidationError("Dùng đối tượng DSAR đã được tenant-scope để ẩn danh hóa.")
    with organization_scope(organization) as organization:
        case = _get_tenant_instance(DSARCase, case, organization)
        if case.has_active_legal_hold:
            raise WorkflowValidationError("Không thể ẩn danh hóa khi legal hold còn hiệu lực.")
        if case.status != DSARCase.Status.COMPLETED:
            raise WorkflowValidationError("Chỉ ẩn danh hóa hồ sơ DSAR đã hoàn tất.")
        case.subject_email = ""
        case.subject_user = None
        case.anonymised_at = timezone.now()
        case.full_clean()
        case.save()
        audit(organization, "dsar.anonymised", actor=actor, instance=case)
        return case


anonymise_case = anonymize_case


def create_legal_hold(*, organization: Organization | str, reason: str, dsar_case: DSARCase | None = None, subject_email: str = "", actor=None) -> LegalHold:
    with organization_scope(organization) as organization:
        if dsar_case is not None:
            dsar_case = _get_tenant_instance(DSARCase, dsar_case, organization)
        hold = LegalHold(
            organization=organization,
            dsar_case=dsar_case,
            subject_email=subject_email.strip().lower(),
            reason=reason.strip(),
            imposed_by=actor,
        )
        hold.full_clean()
        hold.save()
        audit(organization, "legal_hold.created", actor=actor, instance=hold)
        return hold


def release_legal_hold(*, hold: LegalHold | int, actor=None, reason: str) -> LegalHold:
    organization = hold.organization if isinstance(hold, LegalHold) else None
    if organization is None:
        raise WorkflowValidationError("Dùng đối tượng legal hold đã được tenant-scope để giải tỏa.")
    with organization_scope(organization) as organization:
        hold = _get_tenant_instance(LegalHold, hold, organization)
        hold.active = False
        hold.released_at = timezone.now()
        hold.release_reason = reason.strip()
        hold.full_clean()
        hold.save()
        audit(organization, "legal_hold.released", actor=actor, instance=hold)
        return hold


def approve_impact_dossier(*, dossier: ImpactDossier | int, officer, actor=None) -> ImpactDossier:
    organization = dossier.organization if isinstance(dossier, ImpactDossier) else None
    if organization is None:
        raise WorkflowValidationError("Dùng hồ sơ đánh giá đã được tenant-scope để phê duyệt.")
    with organization_scope(organization) as organization:
        require_privacy_officer(organization, officer)
        dossier = _get_tenant_instance(ImpactDossier, dossier, organization)
        dossier.status = ImpactDossier.Status.APPROVED
        dossier.officer_approved_by = officer
        dossier.officer_approved_at = timezone.now()
        dossier.full_clean()
        dossier.save()
        audit(organization, "impact_dossier.approved", actor=actor or officer, instance=dossier)
        return dossier


def mark_transfer_ready(*, transfer: Transfer | int, actor=None) -> Transfer:
    organization = transfer.organization if isinstance(transfer, Transfer) else None
    if organization is None:
        raise WorkflowValidationError("Dùng transfer đã được tenant-scope để gửi rà soát.")
    with organization_scope(organization) as organization:
        transfer = _get_tenant_instance(Transfer, transfer, organization)
        transfer.status = Transfer.Status.READY_FOR_APPROVAL
        transfer.full_clean()
        transfer.save()
        audit(organization, "transfer.ready_for_approval", actor=actor, instance=transfer)
        return transfer


def approve_transfer(*, transfer: Transfer | int, officer, actor=None) -> Transfer:
    organization = transfer.organization if isinstance(transfer, Transfer) else None
    if organization is None:
        raise WorkflowValidationError("Dùng transfer đã được tenant-scope để phê duyệt.")
    with organization_scope(organization) as organization:
        require_privacy_officer(organization, officer)
        transfer = _get_tenant_instance(Transfer, transfer, organization)
        transfer.status = Transfer.Status.APPROVED
        transfer.officer_approved_by = officer
        transfer.officer_approved_at = timezone.now()
        transfer.full_clean()
        transfer.save()
        audit(organization, "transfer.approved", actor=actor or officer, instance=transfer)
        return transfer


def approve_incident(*, incident: Incident | int, officer, actor=None) -> Incident:
    organization = incident.organization if isinstance(incident, Incident) else None
    if organization is None:
        raise WorkflowValidationError("Dùng sự cố đã được tenant-scope để phê duyệt.")
    with organization_scope(organization) as organization:
        require_privacy_officer(organization, officer)
        incident = _get_tenant_instance(Incident, incident, organization)
        if not incident.evidence_items.exists():
            raise WorkflowValidationError("Sự cố cần ít nhất một bằng chứng trước khi phê duyệt.")
        incident.status = Incident.Status.APPROVED
        incident.officer_approved_by = officer
        incident.officer_approved_at = timezone.now()
        incident.full_clean()
        incident.save()
        audit(organization, "incident.approved", actor=actor or officer, instance=incident)
        return incident


def prepare_incident_notification(*, incident: Incident | int, actor=None, draft: str) -> Incident:
    organization = incident.organization if isinstance(incident, Incident) else None
    if organization is None:
        raise WorkflowValidationError("Dùng sự cố đã được tenant-scope để tạo bản nháp.")
    with organization_scope(organization) as organization:
        incident = _get_tenant_instance(Incident, incident, organization)
        if not incident.officer_approved_by_id:
            raise WorkflowValidationError("Privacy Officer phải phê duyệt trước khi tạo bản nháp thông báo.")
        if not incident.evidence_items.exists():
            raise WorkflowValidationError("Sự cố cần ít nhất một bằng chứng.")
        incident.notification_draft = draft.strip()
        incident.status = Incident.Status.REPORTED
        incident.reported_at = timezone.now()
        incident.full_clean()
        incident.save()
        audit(organization, "incident.notification_draft_created", actor=actor, instance=incident)
        return incident


def create_export_artifact(
    *,
    case: DSARCase | int,
    format: str,
    actor=None,
    expires_at=None,
) -> ExportArtifact:
    organization = case.organization if isinstance(case, DSARCase) else None
    if organization is None:
        raise WorkflowValidationError("Dùng DSAR case đã được tenant-scope để tạo tệp xuất.")
    with organization_scope(organization) as organization:
        case = _get_tenant_instance(DSARCase, case, organization)
        if case.requires_officer_approval and not case.officer_approved_by_id:
            raise WorkflowValidationError("Privacy Officer phải phê duyệt DSAR trước khi tạo tệp xuất.")
        if format not in ExportArtifact.Format.values:
            raise WorkflowValidationError("Định dạng xuất không được hỗ trợ.")
        artifact = ExportArtifact(
            organization=organization,
            case=case,
            format=format,
            file_name=f"{case.reference}-{timezone.now():%Y%m%d%H%M%S}.{format}",
            expires_at=expires_at or timezone.now() + timedelta(minutes=int(getattr(settings, "EXPORT_TTL_MINUTES", 15))),
        )
        artifact.full_clean()
        artifact.save()
        audit(organization, "export.requested", actor=actor, instance=artifact, metadata={"format": format})
        return artifact


def approve_export_artifact(*, artifact: ExportArtifact | int, officer, actor=None) -> ExportArtifact:
    organization = artifact.organization if isinstance(artifact, ExportArtifact) else None
    if organization is None:
        raise WorkflowValidationError("Dùng export artifact đã được tenant-scope để phê duyệt.")
    with organization_scope(organization) as organization:
        require_privacy_officer(organization, officer)
        artifact = _get_tenant_instance(ExportArtifact, artifact, organization)
        if artifact.case.requires_officer_approval and not artifact.case.officer_approved_by_id:
            raise WorkflowValidationError("DSAR gốc chưa được Privacy Officer phê duyệt.")
        artifact.status = ExportArtifact.Status.APPROVED
        artifact.approved_by = officer
        artifact.approved_at = timezone.now()
        artifact.full_clean()
        artifact.save()
        audit(organization, "export.approved", actor=actor or officer, instance=artifact)
        return artifact


def generate_export_artifact(*, artifact: ExportArtifact | int, actor=None) -> ExportArtifact:
    """Generate a local educational DOCX/PDF/JSON export after approval."""

    organization = artifact.organization if isinstance(artifact, ExportArtifact) else None
    if organization is None:
        raise WorkflowValidationError("Dùng export artifact đã được tenant-scope để tạo tệp.")
    with organization_scope(organization) as organization:
        artifact = _get_tenant_instance(ExportArtifact, artifact, organization)
        if artifact.status != ExportArtifact.Status.APPROVED:
            raise WorkflowValidationError("Chỉ tệp xuất đã được phê duyệt mới được tạo.")
        from .exports import render_educational_draft

        rendered = render_educational_draft(artifact)
        artifact.status = ExportArtifact.Status.READY
        artifact.storage_path = rendered.relative_name
        artifact.file_name = rendered.file_name
        artifact.document_sha256 = rendered.sha256
        artifact.generated_at = timezone.now()
        artifact.full_clean()
        artifact.save()
        audit(organization, "export.generated", actor=actor, instance=artifact, metadata={"format": artifact.format})
        return artifact


def approve_workflow_item(*, item, officer, actor=None):
    """Small dispatcher used by the portal's generic approval action."""

    if isinstance(item, DSARCase):
        return approve_case(case=item, officer=officer, actor=actor)
    if isinstance(item, Transfer):
        return approve_transfer(transfer=item, officer=officer, actor=actor)
    if isinstance(item, ImpactDossier):
        return approve_impact_dossier(dossier=item, officer=officer, actor=actor)
    if isinstance(item, Incident):
        return approve_incident(incident=item, officer=officer, actor=actor)
    if isinstance(item, ExportArtifact):
        return approve_export_artifact(artifact=item, officer=officer, actor=actor)
    raise WorkflowValidationError("Loại đối tượng không hỗ trợ workflow phê duyệt.")


def verify_audit_chain(
    *,
    organization: Organization | str,
    details: bool = False,
    return_report: bool = False,
):
    """Expose a boolean to the dashboard, with optional errors or full AuditChainReport."""

    report = _verify_audit_chain(organization)
    if return_report:
        return report
    return (report.is_valid, report.errors) if details else report.is_valid


def simulate_audit_tampering(
    *,
    organization: Organization | str,
    sequence: int,
    tampered_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Demonstrate database tampering detection for seminar live presentations.

    Uses direct queryset update to bypass model-level immutable validation guards.
    Returns backup information needed to restore the original record.
    """
    org_id = getattr(organization, "pk", organization)
    event = AuditEvent.all_objects.filter(organization_id=org_id, sequence=sequence).first()
    if not event:
        raise WorkflowValidationError(f"Không tìm thấy AuditEvent tại sequence {sequence}.")

    backup = {
        "event_id": str(event.pk),
        "sequence": event.sequence,
        "original_metadata": dict(event.metadata),
        "original_hash": event.event_hash,
    }

    # Embed original backup inside metadata for 100% deterministic restoration
    injected_metadata = dict(event.metadata)
    injected_metadata["_backup_original_metadata"] = dict(event.metadata)
    injected_metadata["_backup_original_hash"] = event.event_hash
    injected_metadata.update(tampered_metadata or {"_tampered_by": "unauthorized_actor", "illicit_modification": True})

    AuditEvent.all_objects.filter(pk=event.pk).update(metadata=injected_metadata)
    return backup


def restore_audit_event(
    *,
    organization: Organization | str,
    sequence: int,
    original_metadata: dict[str, Any] | None = None,
    original_hash: str | None = None,
) -> bool:
    """Restore an audit event to its pristine cryptographic state after a live demo."""
    org_id = getattr(organization, "pk", organization)
    event = AuditEvent.all_objects.filter(organization_id=org_id, sequence=sequence).first()
    if not event:
        raise WorkflowValidationError(f"Không tìm thấy AuditEvent tại sequence {sequence}.")

    if original_metadata is not None and original_hash is not None:
        AuditEvent.all_objects.filter(pk=event.pk).update(metadata=original_metadata, event_hash=original_hash)
    elif "_backup_original_metadata" in event.metadata and "_backup_original_hash" in event.metadata:
        restored_meta = dict(event.metadata["_backup_original_metadata"])
        restored_hash = str(event.metadata["_backup_original_hash"])
        AuditEvent.all_objects.filter(pk=event.pk).update(metadata=restored_meta, event_hash=restored_hash)
    else:
        # Fallback: Clean illicit demo keys if present
        clean_metadata = dict(event.metadata)
        clean_metadata.pop("_tampered_by", None)
        clean_metadata.pop("illicit_modification", None)
        clean_metadata.pop("_demo_tampered", None)
        clean_metadata.pop("actor_compromised", None)
        event.metadata = clean_metadata
        recalculated = event.calculate_hash()
        AuditEvent.all_objects.filter(pk=event.pk).update(metadata=clean_metadata, event_hash=recalculated)

    return True


