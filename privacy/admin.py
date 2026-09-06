"""Conservative Django admin registrations for the local seminar prototype."""

from __future__ import annotations

from django.contrib import admin

from . import models


class TenantScopedAdmin(admin.ModelAdmin):
    """Show only the selected tenant unless the operator is a superuser."""

    list_select_related = ("organization",)
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        queryset = self.model.all_objects.all()
        if request.user.is_superuser:
            return queryset
        organization_id = request.session.get("active_organization_id")
        return queryset.filter(organization_id=organization_id) if organization_id else queryset.none()

    def has_delete_permission(self, request, obj=None):
        return bool(request.user.is_superuser)


@admin.register(models.Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "status", "gdpr_assessment_required")
    search_fields = ("name", "slug")
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.LegalRule)
class LegalRuleAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "jurisdiction", "active", "legal_review_required")
    list_filter = ("jurisdiction", "active", "legal_review_required")
    search_fields = ("code", "title")
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.RuleVersion)
class RuleVersionAdmin(admin.ModelAdmin):
    list_display = ("legal_rule", "version", "effective_from", "effective_until", "duration_days", "is_current")
    list_filter = ("is_current", "legal_review_required", "legal_rule__jurisdiction")
    readonly_fields = ("created_at", "updated_at")


@admin.register(models.Membership)
class MembershipAdmin(TenantScopedAdmin):
    list_display = ("user", "organization", "role", "status")
    list_filter = ("role", "status")
    search_fields = ("user__username", "user__email", "organization__name")


@admin.register(models.ProcessingActivity)
class ProcessingActivityAdmin(TenantScopedAdmin):
    list_display = ("name", "organization", "legal_role", "status", "gdpr_applicable", "involves_cross_border_transfer")
    list_filter = ("status", "legal_role", "gdpr_applicable")
    search_fields = ("name", "code", "organization__name")


@admin.register(models.ProcessingPurpose, models.DataCategory, models.NoticeVersion, models.Vendor)
class NamedTenantAdmin(TenantScopedAdmin):
    list_display = ("__str__", "organization", "updated_at")
    search_fields = ("name", "organization__name")


@admin.register(models.ConsentEvent)
class ConsentEventAdmin(TenantScopedAdmin):
    list_display = ("subject_email", "purpose", "status", "notice_version", "occurred_at", "organization")
    list_filter = ("status",)
    search_fields = ("subject_email", "purpose__name")
    readonly_fields = TenantScopedAdmin.readonly_fields + ("occurred_at",)
    actions = None

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.DSARCase)
class DSARCaseAdmin(TenantScopedAdmin):
    list_display = ("reference", "subject_email", "request_type", "status", "sla_state", "effective_due_at", "organization")
    list_filter = ("status", "request_type", "sla_state")
    search_fields = ("reference", "subject_email")


@admin.register(models.LegalHold, models.RetentionPolicy, models.Subprocessor)
class TenantRecordAdmin(TenantScopedAdmin):
    list_display = ("__str__", "organization", "updated_at")


@admin.register(models.ImpactDossier, models.ExemptionAssessment, models.Transfer, models.Incident)
class WorkflowAdmin(TenantScopedAdmin):
    list_display = ("__str__", "organization", "status", "updated_at")
    list_filter = ("status",)


@admin.register(models.ExportArtifact)
class ExportArtifactAdmin(TenantScopedAdmin):
    list_display = ("file_name", "case", "status", "expires_at", "organization")
    list_filter = ("status", "format")
    readonly_fields = TenantScopedAdmin.readonly_fields + ("download_token", "document_sha256", "generated_at", "downloaded_at")


@admin.register(models.AuditEvent)
class AuditEventAdmin(TenantScopedAdmin):
    list_display = ("organization", "sequence", "event_type", "object_type", "object_id", "occurred_at")
    list_filter = ("event_type",)
    search_fields = ("event_type", "object_type", "object_id")
    readonly_fields = (
        "organization",
        "sequence",
        "occurred_at",
        "actor",
        "event_type",
        "object_type",
        "object_id",
        "metadata",
        "previous_hash",
        "event_hash",
        "created_at",
        "updated_at",
    )
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


for extra_model in (
    models.LegalEntity,
    models.ProcessingActivityPurpose,
    models.ProcessingActivityDataCategory,
    models.RoleAssignment,
    models.NoticePurpose,
    models.DSARCaseTask,
    models.IncidentEvidence,
    models.TransferDataCategory,
):
    admin.site.register(extra_model, TenantScopedAdmin)
