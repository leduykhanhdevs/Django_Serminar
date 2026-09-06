"""Create idempotent, entirely fictional demo data for the seminar."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from privacy import services
from privacy.models import (
    ConsentEvent,
    DataCategory,
    DSARCase,
    DSARCaseTask,
    ExemptionAssessment,
    ExportArtifact,
    ImpactDossier,
    Incident,
    IncidentEvidence,
    LegalEntity,
    LegalRule,
    Membership,
    NoticePurpose,
    NoticeVersion,
    Organization,
    ProcessingActivity,
    ProcessingActivityDataCategory,
    ProcessingActivityPurpose,
    ProcessingPurpose,
    RetentionPolicy,
    RoleAssignment,
    RuleVersion,
    Subprocessor,
    Transfer,
    TransferDataCategory,
    Vendor,
)


CURRENT_LAW_URL = "https://vanban.chinhphu.vn/?classid=1&docid=214590&pageid=27160&typegroup="
DECREE_356_URL = "https://vanban.chinhphu.vn/default.aspx?docid=216387&pageid=27160"
GDPR_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679"


class Command(BaseCommand):
    help = "Tạo dữ liệu giả lập hai tenant cho Privacy Compliance Hub (không có dữ liệu cá nhân thật)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-exports",
            action="store_true",
            help="Tạo DOCX/PDF bản nháp học tập cho hồ sơ DSAR đã được phê duyệt.",
        )

    def handle(self, *args, **options):
        users = self._seed_users()
        rules = self._seed_rule_catalog()
        an_phuc, _ = Organization.objects.get_or_create(
            slug="an-phuc-demo",
            defaults={
                "name": "Công ty Cổ phần An Phúc (DEMO)",
                "contact_email": "privacy@anphuc.example.test",
                "gdpr_assessment_required": True,
            },
        )
        binh_minh, _ = Organization.objects.get_or_create(
            slug="binh-minh-demo",
            defaults={
                "name": "Công ty TNHH Bình Minh (DEMO)",
                "contact_email": "privacy@binhminh.example.test",
                "gdpr_assessment_required": False,
            },
        )

        an_phuc_case = self._seed_an_phuc(an_phuc, users, rules, with_exports=options["with_exports"])
        self._seed_binh_minh(binh_minh, users, rules)

        self.stdout.write(self.style.SUCCESS("Đã seed dữ liệu hoàn toàn giả lập cho 2 tenant."))
        self.stdout.write("Tenant 1: an-phuc-demo | Tenant 2: binh-minh-demo")
        self.stdout.write(f"DSAR minh họa: {an_phuc_case.reference}")
        self.stdout.write("Tài khoản demo (mật khẩu chung: DemoOnly!2026):")
        for username, label in (
            ("minh.demo", "Data Subject - An Phúc"),
            ("agent.demo", "Case Agent - An Phúc"),
            ("officer.demo", "Privacy Officer - An Phúc"),
            ("admin.demo", "Tenant Admin - An Phúc"),
            ("auditor.demo", "Platform Auditor - hai tenant"),
            ("beta.officer", "Privacy Officer - Bình Minh"),
            ("beta.subject", "Data Subject - Bình Minh"),
        ):
            self.stdout.write(f"  - {username}: {label}")
        if options["with_exports"]:
            self.stdout.write("Đã yêu cầu/tạo bản xuất cục bộ có watermark BẢN NHÁP HỌC TẬP.")
        else:
            self.stdout.write("Dùng --with-exports để tạo DOCX/PDF minh họa sau khi đã seed.")

    def _seed_users(self):
        user_model = get_user_model()
        entries = {
            "subject": ("minh.demo", "minh.demo@anphuc.example.test", "Minh Demo"),
            "agent": ("agent.demo", "agent.demo@anphuc.example.test", "Case Agent Demo"),
            "officer": ("officer.demo", "officer.demo@anphuc.example.test", "Privacy Officer Demo"),
            "admin": ("admin.demo", "admin.demo@anphuc.example.test", "Tenant Admin Demo"),
            "auditor": ("auditor.demo", "auditor.demo@privacyhub.example.test", "Platform Auditor Demo"),
            "beta_officer": ("beta.officer", "officer.demo@binhminh.example.test", "Privacy Officer Bình Minh"),
            "beta_subject": ("beta.subject", "subject.demo@binhminh.example.test", "Chủ thể Bình Minh"),
        }
        users = {}
        for key, (username, email, display_name) in entries.items():
            user, created = user_model.objects.get_or_create(username=username, defaults={"email": email, "first_name": display_name})
            if created:
                user.set_password("DemoOnly!2026")
                user.save(update_fields=["password"])
            users[key] = user
        return users

    def _seed_rule_catalog(self):
        """Seed dated reference rules, never a legal decision engine.

        The days below are deliberately visible, versioned *operational demo*
        settings.  A Privacy Officer must configure business-day calendars,
        exceptions and legal review before relying on them in a real system.
        """

        definitions = (
            ("dsar-response", "DSAR - thời hạn vận hành mặc định", 10, "NĐ 356/2025 Điều 5; cấu hình mẫu học tập"),
            ("dsar-access", "DSAR - xem, sửa hoặc cung cấp", 10, "NĐ 356/2025 Điều 5 khoản 3; cấu hình mẫu học tập"),
            ("dsar-rectification", "DSAR - xem, sửa hoặc cung cấp", 10, "NĐ 356/2025 Điều 5 khoản 3; cấu hình mẫu học tập"),
            ("dsar-portability", "DSAR - xem, sửa hoặc cung cấp", 10, "NĐ 356/2025 Điều 5 khoản 3; cấu hình mẫu học tập"),
            ("dsar-erasure", "DSAR - xóa dữ liệu", 20, "NĐ 356/2025 Điều 5 khoản 4; cấu hình mẫu học tập"),
            ("dsar-restriction", "DSAR - hạn chế xử lý", 15, "NĐ 356/2025 Điều 5 khoản 2; cấu hình mẫu học tập"),
            ("dsar-objection", "DSAR - phản đối xử lý", 15, "NĐ 356/2025 Điều 5 khoản 2; cấu hình mẫu học tập"),
            ("dsar-withdrawal", "DSAR - rút lại đồng ý", 15, "NĐ 356/2025 Điều 5 khoản 2; cấu hình mẫu học tập"),
            ("dsar-protection", "DSAR - biện pháp bảo vệ", 15, "NĐ 356/2025 Điều 5 khoản 5; cấu hình mẫu học tập"),
            ("incident-notification", "Sự cố - mốc thông báo", 3, "Luật 91/2025/QH15 Điều 23; cấu hình 72 giờ minh họa"),
            ("dpia-dossier", "Hồ sơ đánh giá tác động xử lý", 60, "Luật 91/2025/QH15 Điều 21; cấu hình mẫu học tập"),
            ("cross-border-dossier", "Hồ sơ chuyển dữ liệu xuyên biên giới", 60, "Luật 91/2025/QH15 Điều 20; cấu hình mẫu học tập"),
        )
        rules = {}
        for code, title, duration_days, reference in definitions:
            rule, _ = LegalRule.objects.get_or_create(
                code=code,
                defaults={
                    "title": title,
                    "jurisdiction": LegalRule.Jurisdiction.VIETNAM_CURRENT,
                    "description": reference,
                    "legal_review_required": True,
                },
            )
            version, _ = RuleVersion.objects.get_or_create(
                legal_rule=rule,
                version="2026.1-demo",
                defaults={
                    "effective_from": date(2026, 1, 1),
                    "duration_days": duration_days,
                    "source_url": DECREE_356_URL,
                    "source_reference": reference,
                    "is_current": True,
                    "legal_review_required": True,
                },
            )
            rules[code] = version

        historical, _ = LegalRule.objects.get_or_create(
            code="nd13-2023-historical-crosswalk",
            defaults={
                "title": "Nghị định 13/2023/NĐ-CP - đối chiếu lịch sử",
                "jurisdiction": LegalRule.Jurisdiction.VIETNAM_ND13_HISTORY,
                "description": "Chỉ để đối chiếu học thuật; không phải baseline tuân thủ hiện hành.",
                "legal_review_required": True,
            },
        )
        RuleVersion.objects.get_or_create(
            legal_rule=historical,
            version="2023-history",
            defaults={
                "effective_from": date(2023, 7, 1),
                "effective_until": date(2025, 12, 31),
                "source_reference": "NĐ 13/2023/NĐ-CP - trạng thái lịch sử sau 01/01/2026",
                "is_current": False,
                "legal_review_required": True,
            },
        )
        gdpr, _ = LegalRule.objects.get_or_create(
            code="gdpr-scope-assessment",
            defaults={
                "title": "GDPR - đánh giá phạm vi áp dụng",
                "jurisdiction": LegalRule.Jurisdiction.GDPR,
                "description": "Lớp đối chiếu, chỉ áp dụng khi có đánh giá phạm vi thực tế.",
                "legal_review_required": True,
            },
        )
        RuleVersion.objects.get_or_create(
            legal_rule=gdpr,
            version="2016-679-reference",
            defaults={
                "effective_from": date(2018, 5, 25),
                "source_url": GDPR_URL,
                "source_reference": "Regulation (EU) 2016/679; scope requires fact-specific assessment.",
                "is_current": True,
                "legal_review_required": True,
            },
        )
        return rules

    @staticmethod
    def _membership(organization, user, role, display_name):
        return Membership.objects.get_or_create(
            organization=organization,
            user=user,
            defaults={"role": role, "status": Membership.Status.ACTIVE, "display_name": display_name},
        )[0]

    def _seed_an_phuc(self, organization, users, rules, *, with_exports):
        with services.organization_scope(organization):
            subject_membership = self._membership(organization, users["subject"], Membership.Role.DATA_SUBJECT, "Minh Demo")
            agent_membership = self._membership(organization, users["agent"], Membership.Role.CASE_AGENT, "Case Agent Demo")
            officer_membership = self._membership(organization, users["officer"], Membership.Role.PRIVACY_OFFICER, "Privacy Officer Demo")
            self._membership(organization, users["admin"], Membership.Role.TENANT_ADMIN, "Tenant Admin Demo")
            auditor_membership = self._membership(organization, users["auditor"], Membership.Role.PLATFORM_AUDITOR, "Platform Auditor Demo")

            entity, _ = LegalEntity.objects.get_or_create(
                organization=organization,
                name="Công ty Cổ phần An Phúc (pháp nhân giả lập)",
                defaults={
                    "entity_type": LegalEntity.EntityType.CONTROLLER,
                    "country_code": "VN",
                    "registration_reference": "DEMO-AP-2026",
                    "is_primary": True,
                },
            )
            portal_purpose, _ = ProcessingPurpose.objects.get_or_create(
                organization=organization,
                code="privacy-portal",
                defaults={
                    "name": "Vận hành cổng quyền dữ liệu cá nhân",
                    "description": "Tiếp nhận và xử lý yêu cầu quyền dữ liệu trong môi trường demo local.",
                },
            )
            notification_purpose, _ = ProcessingPurpose.objects.get_or_create(
                organization=organization,
                code="dsar-notification",
                defaults={
                    "name": "Thông báo trạng thái DSAR",
                    "description": "Gửi email nội bộ qua Mailpit cho luồng minh họa.",
                },
            )
            contact_category, _ = DataCategory.objects.get_or_create(
                organization=organization,
                code="demo-contact",
                defaults={
                    "name": "Thông tin liên hệ giả lập",
                    "sensitivity": DataCategory.Sensitivity.PERSONAL,
                    "description": "Chỉ dùng email @example.test; không dùng dữ liệu cá nhân thật.",
                },
            )
            workflow_category, _ = DataCategory.objects.get_or_create(
                organization=organization,
                code="demo-workflow-log",
                defaults={
                    "name": "Nhật ký workflow giả lập",
                    "sensitivity": DataCategory.Sensitivity.TECHNICAL,
                    "description": "Metadata thao tác demo; không thu thập telemetry hành vi thật.",
                },
            )
            activity, _ = ProcessingActivity.objects.get_or_create(
                organization=organization,
                code="privacy-hub-demo",
                defaults={
                    "legal_entity": entity,
                    "name": "Vận hành Privacy Compliance Hub (demo)",
                    "legal_role": ProcessingActivity.LegalRole.CONTROLLER,
                    "status": ProcessingActivity.Status.ACTIVE,
                    "description": "Hoạt động giả lập cho seminar; không tự kết luận vai trò pháp lý thực tế.",
                    "retention_period_days": 90,
                    "gdpr_applicable": False,
                    "involves_cross_border_transfer": True,
                },
            )
            for purpose in (portal_purpose, notification_purpose):
                ProcessingActivityPurpose.objects.get_or_create(
                    organization=organization, processing_activity=activity, purpose=purpose
                )
            for category in (contact_category, workflow_category):
                ProcessingActivityDataCategory.objects.get_or_create(
                    organization=organization, processing_activity=activity, data_category=category
                )
            RoleAssignment.objects.get_or_create(
                organization=organization,
                membership=officer_membership,
                role=Membership.Role.PRIVACY_OFFICER,
                scope=RoleAssignment.Scope.ORGANIZATION,
            )
            RoleAssignment.objects.get_or_create(
                organization=organization,
                membership=agent_membership,
                role=Membership.Role.CASE_AGENT,
                scope=RoleAssignment.Scope.PROCESSING_ACTIVITY,
                processing_activity=activity,
            )
            RoleAssignment.objects.get_or_create(
                organization=organization,
                membership=auditor_membership,
                role=Membership.Role.PLATFORM_AUDITOR,
                scope=RoleAssignment.Scope.ORGANIZATION,
            )

            notice, _ = NoticeVersion.objects.get_or_create(
                organization=organization,
                title="Thông báo xử lý dữ liệu cho cổng demo",
                version="2026.1-demo",
                defaults={
                    "body": (
                        "Bản thông báo demo mô tả từng mục đích xử lý. Người dùng phải chọn riêng từng mục đích; "
                        "im lặng hoặc ô chọn mặc định không được xem là đồng ý."
                    ),
                    "status": NoticeVersion.Status.PUBLISHED,
                    "effective_at": timezone.now() - timedelta(days=1),
                    "source_reference": "Luật 91/2025/QH15 và NĐ 356/2025/NĐ-CP - bản học tập",
                },
            )
            for purpose in (portal_purpose, notification_purpose):
                NoticePurpose.objects.get_or_create(organization=organization, notice_version=notice, purpose=purpose)

            if not services.consent_is_active(
                organization=organization,
                subject_email=users["subject"].email,
                purpose=portal_purpose,
            ):
                services.record_consent(
                    organization=organization,
                    subject_email=users["subject"].email,
                    subject_user=users["subject"],
                    purpose=portal_purpose,
                    notice_version=notice,
                    actor=users["subject"],
                    evidence={"channel": "seed_demo", "subject": "fictional", "notice_version": notice.version},
                    evidence_reference="SEED-DEMO-CONSENT-001",
                )

            case = DSARCase.objects.filter(reference="DSAR-DEMO-PORT").first()
            if case is None:
                case = services.create_dsar_case(
                    organization=organization,
                    subject_email=users["subject"].email,
                    subject_user=users["subject"],
                    request_type=DSARCase.RequestType.PORTABILITY,
                    description="Yêu cầu cung cấp dữ liệu hoàn toàn giả lập để trình diễn seminar.",
                    actor=users["subject"],
                    rule_version=rules["dsar-portability"],
                    requires_officer_approval=True,
                )
                case.reference = "DSAR-DEMO-PORT"
                case.save(update_fields=["reference", "updated_at"])
            DSARCaseTask.objects.get_or_create(
                organization=organization,
                dsar_case=case,
                title="Xác minh danh tính bằng tài khoản demo",
                defaults={"assigned_to": users["agent"], "due_at": case.due_at},
            )
            if not case.officer_approved_by_id:
                services.approve_case(case=case, officer=users["officer"], actor=users["officer"], decision_notes="Phê duyệt demo.")
                case.refresh_from_db()

            RetentionPolicy.objects.get_or_create(
                organization=organization,
                name="Ẩn danh DSAR demo sau 90 ngày",
                defaults={
                    "target": RetentionPolicy.Target.DSAR_CASE,
                    "retention_days": 90,
                    "action": RetentionPolicy.Action.ANONYMISE,
                    "processing_activity": activity,
                },
            )
            RetentionPolicy.objects.get_or_create(
                organization=organization,
                name="Thu hồi bản xuất demo sau 1 ngày",
                defaults={
                    "target": RetentionPolicy.Target.EXPORT_ARTIFACT,
                    "retention_days": 1,
                    "action": RetentionPolicy.Action.REVOKE,
                    "processing_activity": activity,
                },
            )

            vendor, _ = Vendor.objects.get_or_create(
                organization=organization,
                name="Aurora Cloud Demo",
                defaults={
                    "country_code": "US",
                    "contact_email": "privacy@aurora-cloud.example.test",
                    "service_description": "Hạ tầng cloud giả lập cho hồ sơ chuyển dữ liệu demo.",
                    "dpa_in_place": True,
                    "contract_reference": "DPA-DEMO-2026-01",
                    "contract_reviewed_at": timezone.now(),
                    "processes_sensitive_data": False,
                    "status": Vendor.Status.APPROVED,
                },
            )
            Subprocessor.objects.get_or_create(
                organization=organization,
                vendor=vendor,
                name="Aurora Backup Demo",
                defaults={
                    "country_code": "SG",
                    "service_description": "Sao lưu giả lập; không kết nối hoặc gửi dữ liệu thật.",
                    "approved": True,
                    "approved_by": users["officer"],
                },
            )
            dossier, _ = ImpactDossier.objects.get_or_create(
                organization=organization,
                title="DPIA - Aurora Cloud Demo",
                defaults={
                    "dossier_type": ImpactDossier.DossierType.CROSS_BORDER,
                    "status": ImpactDossier.Status.READY_FOR_APPROVAL,
                    "processing_activity": activity,
                    "risk_summary": "Rủi ro minh họa: truy cập sai quyền và dữ liệu nằm ngoài Việt Nam.",
                    "mitigations": "DPA, phân quyền, mã hóa, đánh giá pháp lý và kiểm tra vendor.",
                    "assessment_reference": "DPIA-DEMO-2026-01",
                    "requires_legal_review": True,
                },
            )
            if dossier.status != ImpactDossier.Status.APPROVED:
                services.approve_impact_dossier(dossier=dossier, officer=users["officer"], actor=users["officer"])
                dossier.refresh_from_db()
            exemption, _ = ExemptionAssessment.objects.get_or_create(
                organization=organization,
                title="Đánh giá miễn trừ SME - chỉ minh họa",
                defaults={
                    "status": ExemptionAssessment.Status.LEGAL_REVIEW,
                    "processing_activity": activity,
                    "employee_count": 12,
                    "annual_revenue_vnd": 100000000,
                    "basis": "Không tự kết luận miễn trừ. Cần legal review theo Luật 91/2025/QH15 và NĐ 356/2025/NĐ-CP.",
                    "rule_version": rules["dpia-dossier"],
                },
            )
            transfer, _ = Transfer.objects.get_or_create(
                organization=organization,
                title="Chuyển dữ liệu giả lập đến Aurora Cloud Demo",
                defaults={
                    "vendor": vendor,
                    "destination_country": "US",
                    "legal_basis": "Chờ legal review; không phải kết luận tự động.",
                    "data_flow_description": "Metadata DSAR giả lập từ tenant demo đến hạ tầng demo tại US.",
                    "contract_reference": "DPA-DEMO-2026-01",
                    "impact_dossier": dossier,
                    "exemption_assessment": exemption,
                },
            )
            TransferDataCategory.objects.get_or_create(
                organization=organization, transfer=transfer, data_category=contact_category
            )
            if transfer.status != Transfer.Status.APPROVED:
                services.mark_transfer_ready(transfer=transfer, actor=users["agent"])
                services.approve_transfer(transfer=transfer, officer=users["officer"], actor=users["officer"])
                transfer.refresh_from_db()

            incident, _ = Incident.objects.get_or_create(
                organization=organization,
                title="Sự cố demo: quyền tải bị kiểm tra lại",
                defaults={
                    "description": "Sự cố hoàn toàn giả lập để mô tả luồng evidence, countdown và bản nháp thông báo.",
                    "severity": Incident.Severity.MEDIUM,
                    "status": Incident.Status.DETECTED,
                    "detected_at": timezone.now() - timedelta(hours=3),
                    "notification_rule_version": rules["incident-notification"],
                    "notification_due_at": timezone.now() + timedelta(hours=69),
                    "containment_notes": "Đã cô lập tài khoản demo và ghi nhận sự kiện audit.",
                },
            )
            IncidentEvidence.objects.get_or_create(
                organization=organization,
                incident=incident,
                title="Biên bản evidence demo",
                defaults={
                    "file_reference": "evidence/fictional-incident-note.txt",
                    "digest_sha256": "0" * 64,
                    "collected_by": users["agent"],
                    "notes": "Không có tệp hay dữ liệu cá nhân thật.",
                },
            )
            if not incident.officer_approved_by_id:
                services.approve_incident(incident=incident, officer=users["officer"], actor=users["officer"])
                incident.refresh_from_db()
            if incident.status != Incident.Status.REPORTED:
                services.prepare_incident_notification(
                    incident=incident,
                    actor=users["officer"],
                    draft="BẢN NHÁP HỌC TẬP: thông báo sự cố giả lập, không được nộp hoặc gửi chính thức.",
                )

            if with_exports:
                self._ensure_export(case, users["officer"])
            return case

    def _ensure_export(self, case, officer):
        for format_name in (ExportArtifact.Format.DOCX, ExportArtifact.Format.PDF):
            artifact = ExportArtifact.objects.filter(case=case, format=format_name).order_by("-created_at").first()
            if artifact is not None and (
                artifact.expires_at <= timezone.now()
                or artifact.status in {ExportArtifact.Status.EXPIRED, ExportArtifact.Status.REVOKED}
            ):
                artifact = None
            if artifact is None:
                artifact = services.create_export_artifact(case=case, format=format_name, actor=officer)
            elif artifact.status == ExportArtifact.Status.READY and not (Path(settings.EXPORT_ROOT) / artifact.file_name).is_file():
                # A Docker volume or local output folder may have been cleared;
                # retain the audit row but regenerate only after re-approval.
                artifact.status = ExportArtifact.Status.APPROVED
                artifact.storage_path = ""
                artifact.document_sha256 = ""
                artifact.generated_at = None
                artifact.save(update_fields=["status", "storage_path", "document_sha256", "generated_at", "updated_at"])
            if artifact.status == ExportArtifact.Status.PENDING_APPROVAL:
                artifact = services.approve_export_artifact(artifact=artifact, officer=officer, actor=officer)
            if artifact.status == ExportArtifact.Status.APPROVED:
                services.generate_export_artifact(artifact=artifact, actor=officer)

    def _seed_binh_minh(self, organization, users, rules):
        with services.organization_scope(organization):
            self._membership(organization, users["beta_subject"], Membership.Role.DATA_SUBJECT, "Chủ thể Bình Minh")
            self._membership(organization, users["beta_officer"], Membership.Role.PRIVACY_OFFICER, "Privacy Officer Bình Minh")
            self._membership(organization, users["auditor"], Membership.Role.PLATFORM_AUDITOR, "Platform Auditor Demo")
            entity, _ = LegalEntity.objects.get_or_create(
                organization=organization,
                name="Công ty TNHH Bình Minh (pháp nhân giả lập)",
                defaults={"entity_type": LegalEntity.EntityType.CONTROLLER, "country_code": "VN", "is_primary": True},
            )
            purpose, _ = ProcessingPurpose.objects.get_or_create(
                organization=organization,
                code="account-support",
                defaults={"name": "Hỗ trợ tài khoản demo", "description": "Mục đích riêng của tenant Bình Minh."},
            )
            category, _ = DataCategory.objects.get_or_create(
                organization=organization,
                code="demo-account",
                defaults={
                    "name": "Thông tin tài khoản giả lập",
                    "sensitivity": DataCategory.Sensitivity.PERSONAL,
                    "description": "Không có dữ liệu thật.",
                },
            )
            activity, _ = ProcessingActivity.objects.get_or_create(
                organization=organization,
                code="binh-minh-account-support",
                defaults={
                    "legal_entity": entity,
                    "name": "Hỗ trợ tài khoản Bình Minh (demo)",
                    "legal_role": ProcessingActivity.LegalRole.CONTROLLER,
                    "status": ProcessingActivity.Status.ACTIVE,
                    "description": "Dữ liệu riêng tenant để kiểm tra tenant isolation.",
                    "retention_period_days": 60,
                },
            )
            ProcessingActivityPurpose.objects.get_or_create(
                organization=organization, processing_activity=activity, purpose=purpose
            )
            ProcessingActivityDataCategory.objects.get_or_create(
                organization=organization, processing_activity=activity, data_category=category
            )
            NoticeVersion.objects.get_or_create(
                organization=organization,
                title="Thông báo dữ liệu Bình Minh",
                version="2026.1-demo",
                defaults={
                    "body": "Thông báo hoàn toàn giả lập cho tenant Bình Minh.",
                    "status": NoticeVersion.Status.PUBLISHED,
                    "effective_at": timezone.now() - timedelta(days=1),
                    "source_reference": CURRENT_LAW_URL,
                },
            )
