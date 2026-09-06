"""Tenant-aware Celery tasks for operational privacy deadlines and retention."""

from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.utils import timezone

from .models import DSARCase, ExportArtifact, Organization, RetentionPolicy
from .services import anonymize_case, audit, generate_export_artifact, organization_scope


@shared_task(name="privacy.tasks.review_deadlines")
def review_deadlines() -> dict[str, int]:
    """Refresh non-legal operational SLA indicators under each tenant context."""

    now = timezone.now()
    counts = {"organizations": 0, "due_soon": 0, "overdue": 0}
    for organization in Organization.objects.filter(status=Organization.Status.ACTIVE):
        counts["organizations"] += 1
        with organization_scope(organization):
            cases = DSARCase.objects.exclude(status__in=[DSARCase.Status.COMPLETED, DSARCase.Status.CANCELLED])
            for case in cases.iterator():
                due_at = case.effective_due_at
                if not due_at:
                    continue
                if due_at < now:
                    new_state = DSARCase.SlaState.OVERDUE
                    counts["overdue"] += 1
                elif case.extended_due_at:
                    new_state = DSARCase.SlaState.EXTENDED
                elif due_at <= now + timedelta(days=3):
                    new_state = DSARCase.SlaState.DUE_SOON
                    counts["due_soon"] += 1
                else:
                    new_state = DSARCase.SlaState.ON_TRACK
                if case.sla_state != new_state:
                    case.sla_state = new_state
                    case.save(update_fields=["sla_state", "updated_at"])
    return counts


@shared_task(name="privacy.tasks.apply_retention")
def apply_retention() -> dict[str, int]:
    """Apply only reversible/minimized demo retention actions.

    DSAR records are anonymised instead of deleted so the immutable audit ledger
    can still demonstrate accountability.  Active legal holds always win.
    """

    now = timezone.now()
    counts = {"anonymised_cases": 0, "revoked_exports": 0}
    for organization in Organization.objects.filter(status=Organization.Status.ACTIVE):
        with organization_scope(organization):
            policies = RetentionPolicy.objects.filter(active=True)
            for policy in policies.iterator():
                cutoff = now - timedelta(days=policy.retention_days)
                if policy.target == RetentionPolicy.Target.DSAR_CASE:
                    cases = DSARCase.objects.filter(
                        status=DSARCase.Status.COMPLETED,
                        completed_at__lte=cutoff,
                        anonymised_at__isnull=True,
                    )
                    for case in cases.iterator():
                        if case.has_active_legal_hold:
                            continue
                        anonymize_case(case=case)
                        counts["anonymised_cases"] += 1
                elif policy.target == RetentionPolicy.Target.EXPORT_ARTIFACT:
                    artifacts = ExportArtifact.objects.filter(
                        created_at__lte=cutoff,
                        status__in=[ExportArtifact.Status.READY, ExportArtifact.Status.APPROVED],
                    )
                    for artifact in artifacts.iterator():
                        artifact.status = ExportArtifact.Status.REVOKED
                        artifact.save(update_fields=["status", "updated_at"])
                        audit(organization, "export.revoked_by_retention", instance=artifact, metadata={"policy": policy.name})
                        counts["revoked_exports"] += 1
            expired = ExportArtifact.objects.filter(status=ExportArtifact.Status.READY, expires_at__lte=now)
            for artifact in expired.iterator():
                artifact.status = ExportArtifact.Status.EXPIRED
                artifact.save(update_fields=["status", "updated_at"])
                audit(organization, "export.expired", instance=artifact)
    return counts


@shared_task(name="privacy.tasks.generate_export_artifact")
def generate_export_artifact_task(artifact_id: int, organization_id: str) -> int:
    """Generate a pre-approved local export while restoring tenant context."""

    organization = Organization.objects.get(pk=organization_id)
    with organization_scope(organization):
        artifact = ExportArtifact.objects.get(pk=artifact_id)
        generate_export_artifact(artifact=artifact)
        return artifact.pk
