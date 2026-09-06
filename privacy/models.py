"""Core data model for the local Privacy Compliance Hub.

The application deliberately treats legal rules as versioned reference data.
It helps a team document and run a compliance workflow, but it does not make a
legal determination or file material with a regulator.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import MinValueValidator, validate_email
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone

from .tenant_context import get_current_organization_id


User = get_user_model()


def _case_reference() -> str:
    return f"DSAR-{uuid.uuid4().hex[:12].upper()}"


def _export_expiry() -> timezone.datetime:
    minutes = int(getattr(settings, "EXPORT_TTL_MINUTES", 15))
    return timezone.now() + timedelta(minutes=minutes)


def _same_organization(instance: models.Model, related: models.Model | None, field_name: str) -> None:
    """Reject cross-tenant foreign-key graphs before they reach the database."""

    if related is not None and getattr(related, "organization_id", instance.organization_id) != instance.organization_id:
        raise ValidationError({field_name: "Đối tượng liên kết phải thuộc cùng tổ chức."})


class TenantQuerySet(models.QuerySet):
    def for_organization(self, organization: "Organization | str") -> "TenantQuerySet":
        organization_id = getattr(organization, "pk", organization)
        return self.filter(organization_id=organization_id)

    def current_organization(self) -> "TenantQuerySet":
        organization_id = get_current_organization_id()
        return self.for_organization(organization_id) if organization_id else self.none()


class TenantScopedManager(models.Manager.from_queryset(TenantQuerySet)):
    """Default manager that cannot accidentally read across tenants.

    Background jobs and controlled administrative code may use ``all_objects``
    only after explicitly establishing an organization scope.
    """

    use_in_migrations = True

    def get_queryset(self) -> TenantQuerySet:
        return super().get_queryset().current_organization()


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(TimeStampedModel):
    organization = models.ForeignKey(
        "Organization",
        on_delete=models.PROTECT,
        related_name="%(class)s_records",
        db_index=True,
    )

    objects = TenantScopedManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def clean(self) -> None:
        super().clean()
        if not self.organization_id:
            raise ValidationError({"organization": "Tổ chức là bắt buộc."})

    def ensure_current_tenant(self) -> None:
        """Optional guard for service code before a tenant-scoped mutation."""

        current = get_current_organization_id()
        if current and str(self.organization_id) != str(current):
            raise PermissionDenied("Không thể thay đổi dữ liệu của tổ chức khác.")


class Organization(TimeStampedModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Đang hoạt động"
        SUSPENDED = "suspended", "Tạm dừng"
        ARCHIVED = "archived", "Lưu trữ"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=90, unique=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    contact_email = models.EmailField(blank=True)
    gdpr_assessment_required = models.BooleanField(
        default=False,
        help_text="Cờ đánh giá phạm vi; không tự kết luận GDPR áp dụng.",
    )

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class LegalEntity(TenantScopedModel):
    class EntityType(models.TextChoices):
        CONTROLLER = "controller", "Bên kiểm soát dữ liệu"
        PROCESSOR = "processor", "Bên xử lý dữ liệu"
        JOINT_CONTROLLER = "joint_controller", "Đồng kiểm soát dữ liệu"
        OTHER = "other", "Khác"

    name = models.CharField(max_length=180)
    entity_type = models.CharField(max_length=20, choices=EntityType.choices)
    country_code = models.CharField(max_length=2, default="VN")
    registration_reference = models.CharField(max_length=120, blank=True)
    is_primary = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "name"], name="privacy_entity_org_name_uniq"),
            models.UniqueConstraint(
                fields=["organization"], condition=Q(is_primary=True), name="privacy_one_primary_entity_per_org"
            ),
        ]
        ordering = ["name"]

    def clean(self) -> None:
        super().clean()
        self.country_code = self.country_code.upper()
        if len(self.country_code) != 2 or not self.country_code.isalpha():
            raise ValidationError({"country_code": "Dùng mã quốc gia ISO 3166-1 alpha-2."})

    def __str__(self) -> str:
        return self.name


class Membership(TenantScopedModel):
    class Role(models.TextChoices):
        DATA_SUBJECT = "data_subject", "Chủ thể dữ liệu"
        CASE_AGENT = "case_agent", "Chuyên viên xử lý hồ sơ"
        PRIVACY_OFFICER = "privacy_officer", "Privacy Officer"
        TENANT_ADMIN = "tenant_admin", "Quản trị viên tổ chức"
        PLATFORM_AUDITOR = "platform_auditor", "Kiểm toán viên nền tảng"

    class Status(models.TextChoices):
        ACTIVE = "active", "Đang hoạt động"
        INVITED = "invited", "Đã mời"
        SUSPENDED = "suspended", "Tạm dừng"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="privacy_memberships")
    role = models.CharField(max_length=24, choices=Role.choices, default=Role.DATA_SUBJECT)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.ACTIVE)
    display_name = models.CharField(max_length=120, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "user"], name="privacy_membership_org_user_uniq")]
        indexes = [models.Index(fields=["user", "status"])]

    @property
    def can_approve_privacy_workflows(self) -> bool:
        return self.status == self.Status.ACTIVE and self.role == self.Role.PRIVACY_OFFICER

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization}"


class ProcessingPurpose(TenantScopedModel):
    name = models.CharField(max_length=160)
    code = models.SlugField(max_length=70)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="privacy_purpose_org_code_uniq")]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DataCategory(TenantScopedModel):
    class Sensitivity(models.TextChoices):
        PERSONAL = "personal", "Dữ liệu cá nhân"
        SENSITIVE = "sensitive", "Dữ liệu cá nhân nhạy cảm"
        CHILDREN = "children", "Dữ liệu của trẻ em"
        TECHNICAL = "technical", "Dữ liệu kỹ thuật"

    name = models.CharField(max_length=160)
    code = models.SlugField(max_length=70)
    sensitivity = models.CharField(max_length=16, choices=Sensitivity.choices, default=Sensitivity.PERSONAL)
    description = models.TextField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="privacy_category_org_code_uniq")]
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class ProcessingActivity(TenantScopedModel):
    class LegalRole(models.TextChoices):
        CONTROLLER = "controller", "Bên kiểm soát dữ liệu"
        PROCESSOR = "processor", "Bên xử lý dữ liệu"
        JOINT_CONTROLLER = "joint_controller", "Đồng kiểm soát dữ liệu"

    class Status(models.TextChoices):
        DRAFT = "draft", "Bản nháp"
        ACTIVE = "active", "Đang xử lý"
        PAUSED = "paused", "Tạm dừng"
        RETIRED = "retired", "Ngừng áp dụng"

    legal_entity = models.ForeignKey(LegalEntity, on_delete=models.PROTECT, related_name="processing_activities", null=True, blank=True)
    name = models.CharField(max_length=180)
    code = models.SlugField(max_length=70)
    legal_role = models.CharField(max_length=20, choices=LegalRole.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    description = models.TextField(blank=True)
    retention_period_days = models.PositiveIntegerField(null=True, blank=True)
    gdpr_applicable = models.BooleanField(default=False)
    involves_cross_border_transfer = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "code"], name="privacy_activity_org_code_uniq")]
        ordering = ["name"]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.legal_entity, "legal_entity")

    def __str__(self) -> str:
        return self.name


class ProcessingActivityPurpose(TenantScopedModel):
    processing_activity = models.ForeignKey(ProcessingActivity, on_delete=models.CASCADE, related_name="purpose_links")
    purpose = models.ForeignKey(ProcessingPurpose, on_delete=models.PROTECT, related_name="activity_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "processing_activity", "purpose"], name="privacy_activity_purpose_uniq"
            )
        ]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.processing_activity, "processing_activity")
        _same_organization(self, self.purpose, "purpose")


class ProcessingActivityDataCategory(TenantScopedModel):
    processing_activity = models.ForeignKey(ProcessingActivity, on_delete=models.CASCADE, related_name="category_links")
    data_category = models.ForeignKey(DataCategory, on_delete=models.PROTECT, related_name="activity_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "processing_activity", "data_category"], name="privacy_activity_category_uniq"
            )
        ]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.processing_activity, "processing_activity")
        _same_organization(self, self.data_category, "data_category")


class RoleAssignment(TenantScopedModel):
    """Optional scoped role assignment in addition to a member's primary role."""

    class Scope(models.TextChoices):
        ORGANIZATION = "organization", "Toàn tổ chức"
        PROCESSING_ACTIVITY = "processing_activity", "Hoạt động xử lý"
        DSAR = "dsar", "Hồ sơ DSAR"
        INCIDENT = "incident", "Sự cố"

    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.CharField(max_length=24, choices=Membership.Role.choices)
    scope = models.CharField(max_length=24, choices=Scope.choices, default=Scope.ORGANIZATION)
    processing_activity = models.ForeignKey(ProcessingActivity, on_delete=models.CASCADE, null=True, blank=True, related_name="role_assignments")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "membership", "role", "scope", "processing_activity"],
                name="privacy_role_assignment_uniq",
            )
        ]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.membership, "membership")
        _same_organization(self, self.processing_activity, "processing_activity")
        if self.scope == self.Scope.PROCESSING_ACTIVITY and not self.processing_activity_id:
            raise ValidationError({"processing_activity": "Phạm vi hoạt động xử lý cần một hoạt động."})
        if self.scope != self.Scope.PROCESSING_ACTIVITY and self.processing_activity_id:
            raise ValidationError({"processing_activity": "Chỉ dùng hoạt động với phạm vi hoạt động xử lý."})


class NoticeVersion(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Bản nháp"
        PUBLISHED = "published", "Đã công bố"
        RETIRED = "retired", "Đã thay thế"

    title = models.CharField(max_length=180)
    version = models.CharField(max_length=40)
    body = models.TextField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    effective_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    source_reference = models.CharField(max_length=250, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "title", "version"], name="privacy_notice_org_title_version_uniq")
        ]
        ordering = ["title", "-effective_at"]

    @property
    def is_effective(self) -> bool:
        now = timezone.now()
        return self.status == self.Status.PUBLISHED and self.effective_at <= now and (not self.expires_at or self.expires_at > now)

    def clean(self) -> None:
        super().clean()
        if self.expires_at and self.expires_at <= self.effective_at:
            raise ValidationError({"expires_at": "Ngày hết hiệu lực phải sau ngày hiệu lực."})
        if self.status == self.Status.PUBLISHED and not self.body.strip():
            raise ValidationError({"body": "Thông báo công bố phải có nội dung."})

    def __str__(self) -> str:
        return f"{self.title} v{self.version}"


class NoticePurpose(TenantScopedModel):
    notice_version = models.ForeignKey(NoticeVersion, on_delete=models.CASCADE, related_name="purpose_links")
    purpose = models.ForeignKey(ProcessingPurpose, on_delete=models.PROTECT, related_name="notice_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "notice_version", "purpose"], name="privacy_notice_purpose_uniq")
        ]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.notice_version, "notice_version")
        _same_organization(self, self.purpose, "purpose")


class ConsentEvent(TenantScopedModel):
    class Status(models.TextChoices):
        GRANTED = "granted", "Đồng ý"
        WITHDRAWN = "withdrawn", "Đã rút đồng ý"
        RESTRICTED = "restricted", "Đã hạn chế xử lý"

    subject_email = models.EmailField()
    subject_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="consent_events")
    purpose = models.ForeignKey(ProcessingPurpose, on_delete=models.PROTECT, related_name="consent_events")
    notice_version = models.ForeignKey(NoticeVersion, on_delete=models.PROTECT, related_name="consent_events")
    status = models.CharField(max_length=16, choices=Status.choices)
    occurred_at = models.DateTimeField(default=timezone.now)
    evidence_reference = models.CharField(max_length=250, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="recorded_consent_events")

    class Meta:
        indexes = [models.Index(fields=["organization", "subject_email", "purpose", "-occurred_at"])]
        ordering = ["-occurred_at", "-pk"]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.purpose, "purpose")
        _same_organization(self, self.notice_version, "notice_version")
        try:
            validate_email(self.subject_email)
        except ValidationError as exc:
            raise ValidationError({"subject_email": exc.messages}) from exc
        if self.status == self.Status.GRANTED and not self.notice_version.is_effective:
            raise ValidationError({"notice_version": "Chỉ có thể ghi nhận đồng ý với thông báo đang hiệu lực."})

    @classmethod
    def current_for(cls, organization: Organization | str, subject_email: str, purpose: ProcessingPurpose) -> "ConsentEvent | None":
        return (
            cls.all_objects.filter(
                organization_id=getattr(organization, "pk", organization), subject_email__iexact=subject_email, purpose=purpose
            )
            .order_by("-occurred_at", "-pk")
            .first()
        )


class LegalRule(TimeStampedModel):
    """A reference rule. It is intentionally global, not tenant operational data."""

    class Jurisdiction(models.TextChoices):
        VIETNAM_CURRENT = "vn_current", "Việt Nam hiện hành"
        VIETNAM_ND13_HISTORY = "vn_nd13_history", "NĐ 13/2023 (đối chiếu lịch sử)"
        GDPR = "gdpr", "GDPR"
        INTERNAL = "internal", "Quy tắc vận hành nội bộ"

    code = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=220)
    jurisdiction = models.CharField(max_length=24, choices=Jurisdiction.choices)
    description = models.TextField(blank=True)
    legal_review_required = models.BooleanField(default=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["jurisdiction", "code"]

    def __str__(self) -> str:
        return self.code


class RuleVersion(TimeStampedModel):
    legal_rule = models.ForeignKey(LegalRule, on_delete=models.CASCADE, related_name="versions")
    version = models.CharField(max_length=40)
    effective_from = models.DateField()
    effective_until = models.DateField(null=True, blank=True)
    duration_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Mốc vận hành bằng ngày dương lịch nếu quy tắc quy định một thời hạn.",
    )
    source_url = models.URLField(blank=True)
    source_reference = models.CharField(max_length=250, blank=True)
    is_current = models.BooleanField(default=True)
    legal_review_required = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["legal_rule", "version"], name="privacy_rule_version_uniq")]
        ordering = ["legal_rule__code", "-effective_from"]

    def clean(self) -> None:
        super().clean()
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValidationError({"effective_until": "Ngày kết thúc không thể trước ngày bắt đầu."})

    def applies_on(self, when) -> bool:
        return self.effective_from <= when and (self.effective_until is None or self.effective_until >= when)

    def __str__(self) -> str:
        return f"{self.legal_rule.code} {self.version}"


class DSARCase(TenantScopedModel):
    class RequestType(models.TextChoices):
        ACCESS = "access", "Yêu cầu truy cập"
        RECTIFICATION = "rectification", "Yêu cầu chỉnh sửa"
        PORTABILITY = "portability", "Yêu cầu cung cấp dữ liệu"
        ERASURE = "erasure", "Yêu cầu xóa"
        RESTRICTION = "restriction", "Yêu cầu hạn chế xử lý"
        OBJECTION = "objection", "Yêu cầu phản đối"
        WITHDRAWAL = "withdrawal", "Rút sự đồng ý"
        PROTECTION = "protection", "Yêu cầu bảo vệ dữ liệu"

    class Status(models.TextChoices):
        DRAFT = "draft", "Bản nháp"
        SUBMITTED = "submitted", "Đã tiếp nhận"
        IDENTITY_VERIFIED = "identity_verified", "Đã xác thực danh tính"
        IN_REVIEW = "in_review", "Đang xử lý"
        PENDING_OFFICER_APPROVAL = "pending_officer_approval", "Chờ Privacy Officer phê duyệt"
        APPROVED = "approved", "Đã phê duyệt"
        REJECTED = "rejected", "Từ chối"
        COMPLETED = "completed", "Hoàn tất"
        CANCELLED = "cancelled", "Đã hủy"

    class SlaState(models.TextChoices):
        NOT_STARTED = "not_started", "Chưa bắt đầu"
        ON_TRACK = "on_track", "Đúng hạn"
        DUE_SOON = "due_soon", "Sắp đến hạn"
        EXTENDED = "extended", "Đã gia hạn"
        OVERDUE = "overdue", "Quá hạn"

    reference = models.CharField(max_length=24, default=_case_reference, editable=False)
    subject_email = models.EmailField(blank=True)
    subject_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dsar_cases")
    request_type = models.CharField(max_length=20, choices=RequestType.choices)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    sla_state = models.CharField(max_length=16, choices=SlaState.choices, default=SlaState.NOT_STARTED)
    rule_version = models.ForeignKey(RuleVersion, on_delete=models.PROTECT, null=True, blank=True, related_name="dsar_cases")
    submitted_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    extended_due_at = models.DateTimeField(null=True, blank=True)
    extension_reason = models.TextField(blank=True)
    extension_granted_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_dsar_cases")
    requires_officer_approval = models.BooleanField(default=True)
    officer_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_dsar_cases")
    officer_approved_at = models.DateTimeField(null=True, blank=True)
    decision_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    anonymised_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "reference"], name="privacy_dsar_org_reference_uniq")]
        indexes = [
            models.Index(fields=["organization", "status", "due_at"]),
            models.Index(fields=["organization", "subject_email"]),
        ]
        ordering = ["-submitted_at", "-created_at"]

    @property
    def effective_due_at(self):
        return self.extended_due_at or self.due_at

    @property
    def is_overdue(self) -> bool:
        return bool(self.effective_due_at and self.status not in {self.Status.COMPLETED, self.Status.CANCELLED} and self.effective_due_at < timezone.now())

    @property
    def has_active_legal_hold(self) -> bool:
        return LegalHold.all_objects.filter(organization_id=self.organization_id, active=True).filter(
            Q(dsar_case=self) | Q(dsar_case__isnull=True, subject_email__iexact=self.subject_email)
        ).exists()

    def clean(self) -> None:
        super().clean()
        if not self.subject_email and not self.anonymised_at:
            raise ValidationError({"subject_email": "Email chủ thể là bắt buộc trước khi ẩn danh hóa."})
        if self.status != self.Status.DRAFT and (not self.submitted_at or not self.due_at or not self.rule_version_id):
            raise ValidationError("Hồ sơ đã nộp cần thời điểm nộp, hạn xử lý và phiên bản quy tắc.")
        if self.due_at and self.submitted_at and self.due_at < self.submitted_at:
            raise ValidationError({"due_at": "Hạn xử lý không thể trước thời điểm tiếp nhận."})
        if bool(self.extended_due_at) != bool(self.extension_reason.strip()):
            raise ValidationError("Gia hạn phải có cả hạn mới và lý do bằng văn bản.")
        if self.extended_due_at and self.due_at and self.extended_due_at <= self.due_at:
            raise ValidationError({"extended_due_at": "Hạn gia hạn phải sau hạn ban đầu."})
        if self.assigned_to_id and not Membership.all_objects.filter(
            organization_id=self.organization_id, user_id=self.assigned_to_id, status=Membership.Status.ACTIVE
        ).exists():
            raise ValidationError({"assigned_to": "Người xử lý phải là thành viên đang hoạt động của tổ chức."})
        if self.officer_approved_by_id and not _is_privacy_officer(self.organization_id, self.officer_approved_by_id):
            raise ValidationError({"officer_approved_by": "Chỉ Privacy Officer đang hoạt động được phê duyệt."})
        if self.status in {self.Status.APPROVED, self.Status.COMPLETED} and self.requires_officer_approval and not self.officer_approved_by_id:
            raise ValidationError("Hồ sơ này cần Privacy Officer phê duyệt trước khi hoàn tất.")

    def __str__(self) -> str:
        return self.reference


class DSARCaseTask(TenantScopedModel):
    class Status(models.TextChoices):
        OPEN = "open", "Chưa xử lý"
        IN_PROGRESS = "in_progress", "Đang xử lý"
        BLOCKED = "blocked", "Bị chặn"
        DONE = "done", "Hoàn tất"

    dsar_case = models.ForeignKey(DSARCase, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=180)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="dsar_tasks")
    due_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_at", "created_at"]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.dsar_case, "dsar_case")
        if self.assigned_to_id and not Membership.all_objects.filter(
            organization_id=self.organization_id, user_id=self.assigned_to_id, status=Membership.Status.ACTIVE
        ).exists():
            raise ValidationError({"assigned_to": "Người xử lý phải là thành viên đang hoạt động."})
        if self.status == self.Status.DONE and not self.completed_at:
            raise ValidationError({"completed_at": "Task hoàn tất cần thời điểm hoàn tất."})


class LegalHold(TenantScopedModel):
    dsar_case = models.ForeignKey(DSARCase, on_delete=models.CASCADE, null=True, blank=True, related_name="legal_holds")
    subject_email = models.EmailField(blank=True)
    reason = models.TextField()
    active = models.BooleanField(default=True)
    imposed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="imposed_legal_holds")
    imposed_at = models.DateTimeField(default=timezone.now)
    released_at = models.DateTimeField(null=True, blank=True)
    release_reason = models.TextField(blank=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "active", "subject_email"])]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.dsar_case, "dsar_case")
        if not self.dsar_case_id and not self.subject_email:
            raise ValidationError("Legal hold cần hồ sơ DSAR hoặc email chủ thể.")
        if self.active and self.released_at:
            raise ValidationError({"released_at": "Legal hold đang hiệu lực không thể có thời điểm giải tỏa."})
        if not self.active and (not self.released_at or not self.release_reason.strip()):
            raise ValidationError("Giải tỏa legal hold cần thời điểm và lý do.")


class RetentionPolicy(TenantScopedModel):
    class Target(models.TextChoices):
        DSAR_CASE = "dsar_case", "Hồ sơ DSAR"
        EXPORT_ARTIFACT = "export_artifact", "Tệp xuất"

    class Action(models.TextChoices):
        ANONYMISE = "anonymise", "Ẩn danh hóa"
        REVOKE = "revoke", "Thu hồi tệp"

    name = models.CharField(max_length=160)
    target = models.CharField(max_length=24, choices=Target.choices)
    retention_days = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    action = models.CharField(max_length=16, choices=Action.choices)
    processing_activity = models.ForeignKey(ProcessingActivity, on_delete=models.SET_NULL, null=True, blank=True, related_name="retention_policies")
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="privacy_retention_policy_name_uniq")]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.processing_activity, "processing_activity")
        if self.target == self.Target.DSAR_CASE and self.action != self.Action.ANONYMISE:
            raise ValidationError({"action": "Hồ sơ DSAR chỉ hỗ trợ ẩn danh hóa để giữ bằng chứng audit."})
        if self.target == self.Target.EXPORT_ARTIFACT and self.action != self.Action.REVOKE:
            raise ValidationError({"action": "Tệp xuất chỉ hỗ trợ thu hồi trong bản demo."})


class Vendor(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Bản nháp"
        UNDER_REVIEW = "under_review", "Đang đánh giá"
        APPROVED = "approved", "Đã phê duyệt"
        SUSPENDED = "suspended", "Tạm dừng"

    name = models.CharField(max_length=180)
    country_code = models.CharField(max_length=2)
    contact_email = models.EmailField(blank=True)
    service_description = models.TextField(blank=True)
    dpa_in_place = models.BooleanField(default=False)
    contract_reference = models.CharField(max_length=180, blank=True)
    contract_reviewed_at = models.DateTimeField(null=True, blank=True)
    processes_sensitive_data = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "name"], name="privacy_vendor_org_name_uniq")]
        ordering = ["name"]

    def clean(self) -> None:
        super().clean()
        self.country_code = self.country_code.upper()
        if len(self.country_code) != 2 or not self.country_code.isalpha():
            raise ValidationError({"country_code": "Dùng mã quốc gia ISO 3166-1 alpha-2."})
        if self.status == self.Status.APPROVED and (not self.dpa_in_place or not self.contract_reference.strip()):
            raise ValidationError("Vendor chỉ được phê duyệt khi có DPA và mã tham chiếu hợp đồng.")

    def __str__(self) -> str:
        return self.name


class Subprocessor(TenantScopedModel):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="subprocessors")
    name = models.CharField(max_length=180)
    country_code = models.CharField(max_length=2)
    service_description = models.TextField(blank=True)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_subprocessors")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "vendor", "name"], name="privacy_subprocessor_uniq")]
        ordering = ["vendor__name", "name"]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.vendor, "vendor")
        self.country_code = self.country_code.upper()
        if self.approved and not self.approved_by_id:
            raise ValidationError("Subprocessor được phê duyệt cần người phê duyệt.")
        if self.approved_by_id and not _is_privacy_officer(self.organization_id, self.approved_by_id):
            raise ValidationError({"approved_by": "Chỉ Privacy Officer được phê duyệt."})


class ImpactDossier(TenantScopedModel):
    class DossierType(models.TextChoices):
        DPIA = "dpia", "Đánh giá tác động xử lý"
        CROSS_BORDER = "cross_border", "Hồ sơ chuyển dữ liệu xuyên biên giới"
        INCIDENT = "incident", "Đánh giá sự cố"

    class Status(models.TextChoices):
        DRAFT = "draft", "Bản nháp"
        IN_REVIEW = "in_review", "Đang đánh giá"
        READY_FOR_APPROVAL = "ready_for_approval", "Chờ phê duyệt"
        APPROVED = "approved", "Đã phê duyệt"
        REJECTED = "rejected", "Từ chối"

    title = models.CharField(max_length=180)
    dossier_type = models.CharField(max_length=20, choices=DossierType.choices)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    processing_activity = models.ForeignKey(ProcessingActivity, on_delete=models.SET_NULL, null=True, blank=True, related_name="impact_dossiers")
    risk_summary = models.TextField(blank=True)
    mitigations = models.TextField(blank=True)
    assessment_reference = models.CharField(max_length=180, blank=True)
    requires_legal_review = models.BooleanField(default=True)
    officer_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_impact_dossiers")
    officer_approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.processing_activity, "processing_activity")
        if self.status in {self.Status.READY_FOR_APPROVAL, self.Status.APPROVED} and not self.risk_summary.strip():
            raise ValidationError({"risk_summary": "Hồ sơ sẵn sàng phải có tóm tắt rủi ro."})
        if self.status == self.Status.APPROVED and not self.officer_approved_by_id:
            raise ValidationError("Hồ sơ chỉ được phê duyệt bởi Privacy Officer.")
        if self.officer_approved_by_id and not _is_privacy_officer(self.organization_id, self.officer_approved_by_id):
            raise ValidationError({"officer_approved_by": "Chỉ Privacy Officer được phê duyệt."})

    def __str__(self) -> str:
        return self.title


class ExemptionAssessment(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Bản nháp"
        ASSESSING = "assessing", "Đang đánh giá"
        ELIGIBLE = "eligible", "Có thể áp dụng miễn trừ"
        NOT_ELIGIBLE = "not_eligible", "Không đủ điều kiện"
        LEGAL_REVIEW = "legal_review", "Cần legal review"

    title = models.CharField(max_length=180)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT)
    processing_activity = models.ForeignKey(ProcessingActivity, on_delete=models.SET_NULL, null=True, blank=True, related_name="exemption_assessments")
    employee_count = models.PositiveIntegerField(null=True, blank=True)
    annual_revenue_vnd = models.DecimalField(max_digits=18, decimal_places=0, null=True, blank=True)
    basis = models.TextField(blank=True)
    rule_version = models.ForeignKey(RuleVersion, on_delete=models.PROTECT, null=True, blank=True, related_name="exemption_assessments")
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_exemption_assessments")
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.processing_activity, "processing_activity")
        if self.status in {self.Status.ELIGIBLE, self.Status.NOT_ELIGIBLE} and not self.basis.strip():
            raise ValidationError({"basis": "Kết quả đánh giá phải nêu căn cứ và cần legal review."})
        if self.reviewed_by_id and not _is_privacy_officer(self.organization_id, self.reviewed_by_id):
            raise ValidationError({"reviewed_by": "Chỉ Privacy Officer được xác nhận đánh giá."})


class Transfer(TenantScopedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Bản nháp"
        IN_REVIEW = "in_review", "Đang đánh giá"
        READY_FOR_APPROVAL = "ready_for_approval", "Đủ hồ sơ, chờ phê duyệt"
        APPROVED = "approved", "Đã phê duyệt"
        BLOCKED = "blocked", "Bị chặn"

    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="transfers")
    title = models.CharField(max_length=180)
    destination_country = models.CharField(max_length=2)
    legal_basis = models.CharField(max_length=180, blank=True)
    data_flow_description = models.TextField(blank=True)
    contract_reference = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT)
    impact_dossier = models.ForeignKey(ImpactDossier, on_delete=models.PROTECT, null=True, blank=True, related_name="transfers")
    exemption_assessment = models.ForeignKey(ExemptionAssessment, on_delete=models.PROTECT, null=True, blank=True, related_name="transfers")
    officer_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_transfers")
    officer_approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.vendor, "vendor")
        _same_organization(self, self.impact_dossier, "impact_dossier")
        _same_organization(self, self.exemption_assessment, "exemption_assessment")
        self.destination_country = self.destination_country.upper()
        if len(self.destination_country) != 2 or not self.destination_country.isalpha():
            raise ValidationError({"destination_country": "Dùng mã quốc gia ISO 3166-1 alpha-2."})
        if self.status in {self.Status.READY_FOR_APPROVAL, self.Status.APPROVED}:
            missing = []
            if not self.vendor.dpa_in_place:
                missing.append("DPA với vendor")
            if not (self.contract_reference.strip() or self.vendor.contract_reference.strip()):
                missing.append("mã tham chiếu hợp đồng")
            if not self.data_flow_description.strip():
                missing.append("mô tả luồng dữ liệu")
            if not self.impact_dossier_id or self.impact_dossier.status != ImpactDossier.Status.APPROVED:
                missing.append("hồ sơ đánh giá tác động đã phê duyệt")
            if missing:
                raise ValidationError("Chưa thể chuyển trạng thái sẵn sàng: thiếu " + ", ".join(missing) + ".")
        if self.status == self.Status.APPROVED and not self.officer_approved_by_id:
            raise ValidationError("Chuyển dữ liệu cần Privacy Officer phê duyệt.")
        if self.officer_approved_by_id and not _is_privacy_officer(self.organization_id, self.officer_approved_by_id):
            raise ValidationError({"officer_approved_by": "Chỉ Privacy Officer được phê duyệt."})

    def __str__(self) -> str:
        return self.title


class TransferDataCategory(TenantScopedModel):
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name="category_links")
    data_category = models.ForeignKey(DataCategory, on_delete=models.PROTECT, related_name="transfer_links")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["organization", "transfer", "data_category"], name="privacy_transfer_category_uniq")
        ]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.transfer, "transfer")
        _same_organization(self, self.data_category, "data_category")


class Incident(TenantScopedModel):
    class Severity(models.TextChoices):
        LOW = "low", "Thấp"
        MEDIUM = "medium", "Trung bình"
        HIGH = "high", "Cao"
        CRITICAL = "critical", "Nghiêm trọng"

    class Status(models.TextChoices):
        DETECTED = "detected", "Đã phát hiện"
        INVESTIGATING = "investigating", "Đang điều tra"
        PENDING_OFFICER_APPROVAL = "pending_officer_approval", "Chờ Privacy Officer phê duyệt"
        APPROVED = "approved", "Đã phê duyệt phương án"
        REPORTED = "reported", "Đã tạo bản nháp thông báo"
        CONTAINED = "contained", "Đã cô lập"
        CLOSED = "closed", "Đã đóng"

    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=16, choices=Severity.choices, default=Severity.MEDIUM)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DETECTED)
    detected_at = models.DateTimeField(default=timezone.now)
    notification_rule_version = models.ForeignKey(RuleVersion, on_delete=models.PROTECT, null=True, blank=True, related_name="incidents")
    notification_due_at = models.DateTimeField(null=True, blank=True)
    notification_draft = models.TextField(blank=True)
    containment_notes = models.TextField(blank=True)
    officer_approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_incidents")
    officer_approved_at = models.DateTimeField(null=True, blank=True)
    reported_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "status", "notification_due_at"])]
        ordering = ["-detected_at"]

    def clean(self) -> None:
        super().clean()
        if self.notification_due_at and self.notification_due_at < self.detected_at:
            raise ValidationError({"notification_due_at": "Hạn thông báo không thể trước thời điểm phát hiện."})
        if self.status in {self.Status.APPROVED, self.Status.REPORTED, self.Status.CLOSED} and not self.officer_approved_by_id:
            raise ValidationError("Sự cố cần Privacy Officer phê duyệt trước khi báo cáo hoặc đóng.")
        if self.officer_approved_by_id and not _is_privacy_officer(self.organization_id, self.officer_approved_by_id):
            raise ValidationError({"officer_approved_by": "Chỉ Privacy Officer được phê duyệt."})
        if self.status == self.Status.REPORTED and not self.notification_draft.strip():
            raise ValidationError({"notification_draft": "Trạng thái báo cáo cần bản nháp thông báo."})

    @property
    def is_notification_overdue(self) -> bool:
        return bool(self.notification_due_at and self.status not in {self.Status.REPORTED, self.Status.CLOSED} and self.notification_due_at < timezone.now())

    def __str__(self) -> str:
        return self.title


class IncidentEvidence(TenantScopedModel):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name="evidence_items")
    title = models.CharField(max_length=180)
    file_reference = models.CharField(max_length=300, blank=True)
    digest_sha256 = models.CharField(max_length=64, blank=True)
    collected_at = models.DateTimeField(default=timezone.now)
    collected_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="collected_incident_evidence")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["collected_at"]

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.incident, "incident")
        if self.digest_sha256 and (len(self.digest_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.digest_sha256.lower())):
            raise ValidationError({"digest_sha256": "Digest phải là SHA-256 hex 64 ký tự."})


class ExportArtifact(TenantScopedModel):
    class Format(models.TextChoices):
        PDF = "pdf", "PDF"
        DOCX = "docx", "DOCX"
        JSON = "json", "JSON"

    class Status(models.TextChoices):
        PENDING_APPROVAL = "pending_approval", "Chờ phê duyệt"
        APPROVED = "approved", "Đã phê duyệt"
        GENERATING = "generating", "Đang tạo"
        READY = "ready", "Đã tạo, sẵn sàng tải"
        EXPIRED = "expired", "Đã hết hạn"
        REVOKED = "revoked", "Đã thu hồi"

    case = models.ForeignKey(DSARCase, on_delete=models.CASCADE, related_name="export_artifacts")
    file_name = models.CharField(max_length=180)
    format = models.CharField(max_length=8, choices=Format.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_APPROVAL)
    storage_path = models.CharField(max_length=500, blank=True)
    document_sha256 = models.CharField(max_length=64, blank=True)
    download_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    expires_at = models.DateTimeField(default=_export_expiry)
    requires_reauthentication = models.BooleanField(default=True)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_exports")
    approved_at = models.DateTimeField(null=True, blank=True)
    generated_at = models.DateTimeField(null=True, blank=True)
    downloaded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["organization", "status", "expires_at"])]
        ordering = ["-created_at"]

    @property
    def is_available(self) -> bool:
        return self.status == self.Status.READY and self.expires_at > timezone.now()

    @property
    def dsar_case(self) -> DSARCase:
        """Semantic alias used by the service layer; UI can use ``case``."""

        return self.case

    def clean(self) -> None:
        super().clean()
        _same_organization(self, self.case, "case")
        if self.status in {self.Status.APPROVED, self.Status.GENERATING, self.Status.READY} and not self.approved_by_id:
            raise ValidationError("Tệp xuất cần Privacy Officer phê duyệt.")
        if self.approved_by_id and not _is_privacy_officer(self.organization_id, self.approved_by_id):
            raise ValidationError({"approved_by": "Chỉ Privacy Officer được phê duyệt."})
        if self.status == self.Status.READY and (not self.storage_path or not self.generated_at):
            raise ValidationError("Tệp đã tạo cần đường dẫn lưu trữ và thời điểm tạo.")
        if self.document_sha256 and (len(self.document_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.document_sha256.lower())):
            raise ValidationError({"document_sha256": "Digest phải là SHA-256 hex 64 ký tự."})

    def __str__(self) -> str:
        return self.file_name


def _is_privacy_officer(organization_id: str | uuid.UUID, user_id: int | None) -> bool:
    if not user_id:
        return False
    if Membership.all_objects.filter(
        organization_id=organization_id,
        user_id=user_id,
        role=Membership.Role.PRIVACY_OFFICER,
        status=Membership.Status.ACTIVE,
    ).exists():
        return True
    return RoleAssignment.all_objects.filter(
        organization_id=organization_id,
        membership__user_id=user_id,
        membership__status=Membership.Status.ACTIVE,
        role=Membership.Role.PRIVACY_OFFICER,
        scope=RoleAssignment.Scope.ORGANIZATION,
    ).exists()


class AuditEvent(TenantScopedModel):
    """Append-only, per-organization audit ledger with a SHA-256 hash chain."""

    sequence = models.PositiveBigIntegerField(editable=False)
    occurred_at = models.DateTimeField(default=timezone.now, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="privacy_audit_events")
    event_type = models.CharField(max_length=120)
    object_type = models.CharField(max_length=120, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    previous_hash = models.CharField(max_length=64, blank=True, editable=False)
    event_hash = models.CharField(max_length=64, unique=True, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "sequence"], name="privacy_audit_org_sequence_uniq")]
        ordering = ["organization_id", "sequence"]

    def _payload(self) -> dict[str, Any]:
        return {
            "organization_id": str(self.organization_id),
            "sequence": self.sequence,
            "occurred_at": self.occurred_at.isoformat(),
            "actor_id": self.actor_id,
            "event_type": self.event_type,
            "object_type": self.object_type,
            "object_id": self.object_id,
            "metadata": self.metadata,
            "previous_hash": self.previous_hash,
        }

    def calculate_hash(self) -> str:
        body = json.dumps(self._payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    @classmethod
    def append(
        cls,
        *,
        organization: Organization,
        event_type: str,
        actor: User | None = None,
        instance: models.Model | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "AuditEvent":
        """Append one immutable event while serializing writers per organization."""

        with transaction.atomic():
            locked_org = Organization.objects.select_for_update().get(pk=organization.pk)
            previous = cls.all_objects.filter(organization=locked_org).order_by("-sequence").first()
            event = cls(
                organization=locked_org,
                sequence=(previous.sequence + 1) if previous else 1,
                actor=actor,
                event_type=event_type,
                object_type=instance._meta.label if instance is not None else "",
                object_id=str(instance.pk) if instance is not None and instance.pk else "",
                metadata=metadata or {},
                previous_hash=previous.event_hash if previous else "",
            )
            event.event_hash = event.calculate_hash()
            event.full_clean()
            models.Model.save(event, force_insert=True)
            return event

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("AuditEvent là bản ghi bất biến, không thể chỉnh sửa.")
        if not self.sequence:
            previous = self.__class__.all_objects.filter(organization_id=self.organization_id).order_by("-sequence").first()
            self.sequence = (previous.sequence + 1) if previous else 1
            self.previous_hash = previous.event_hash if previous else ""
        self.event_hash = self.calculate_hash()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover - direct safety guard
        raise ValidationError("AuditEvent là bản ghi bất biến, không thể xóa.")


def verify_audit_chain(organization: Organization | str) -> tuple[bool, list[str]]:
    """Return whether a ledger is intact and human-readable integrity errors."""

    organization_id = getattr(organization, "pk", organization)
    errors: list[str] = []
    previous_hash = ""
    expected_sequence = 1
    for event in AuditEvent.all_objects.filter(organization_id=organization_id).order_by("sequence"):
        if event.sequence != expected_sequence:
            errors.append(f"Chuỗi audit thiếu hoặc lặp tại sequence {event.sequence}.")
        if event.previous_hash != previous_hash:
            errors.append(f"Liên kết hash trước không hợp lệ tại sequence {event.sequence}.")
        if event.event_hash != event.calculate_hash():
            errors.append(f"Hash audit không hợp lệ tại sequence {event.sequence}.")
        previous_hash = event.event_hash
        expected_sequence += 1
    return (not errors, errors)
