"""Workflow and isolation checks beyond the small domain smoke tests."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice

from privacy.forms import ConsentSelectionForm
from privacy.models import (
    DataCategory,
    DSARCase,
    ExportArtifact,
    ImpactDossier,
    Incident,
    IncidentEvidence,
    LegalRule,
    Membership,
    NoticeVersion,
    Organization,
    ProcessingPurpose,
    RuleVersion,
    Transfer,
    Vendor,
)
from privacy.services import (
    WorkflowValidationError,
    anonymize_case,
    approve_case,
    approve_export_artifact,
    approve_incident,
    complete_case,
    consent_is_active,
    create_dsar_case,
    create_export_artifact,
    create_legal_hold,
    generate_export_artifact,
    mark_transfer_ready,
    prepare_incident_notification,
    record_consent,
    release_legal_hold,
    withdraw_consent,
)
from privacy.tasks import review_deadlines
from privacy.tenant_context import tenant_context


class PrivacyWorkflowTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.org_a = Organization.objects.create(name="Tenant A giả lập", slug="tenant-a-demo")
        self.org_b = Organization.objects.create(name="Tenant B giả lập", slug="tenant-b-demo")
        self.subject = user_model.objects.create_user("subject-a", "subject-a@example.test", "DemoOnly!2026")
        self.other_subject = user_model.objects.create_user("subject-b", "subject-b@example.test", "DemoOnly!2026")
        self.officer = user_model.objects.create_user("officer-a", "officer-a@example.test", "DemoOnly!2026")
        Membership.all_objects.create(organization=self.org_a, user=self.subject, role=Membership.Role.DATA_SUBJECT)
        Membership.all_objects.create(organization=self.org_a, user=self.other_subject, role=Membership.Role.DATA_SUBJECT)
        Membership.all_objects.create(organization=self.org_a, user=self.officer, role=Membership.Role.PRIVACY_OFFICER)

        with tenant_context(str(self.org_a.pk)):
            self.purpose_a = ProcessingPurpose.objects.create(
                organization=self.org_a, name="Hỗ trợ demo", code="support-demo"
            )
            self.notice_a = NoticeVersion.objects.create(
                organization=self.org_a,
                title="Thông báo A",
                version="2026.1",
                body="Nội dung thông báo giả lập.",
                status=NoticeVersion.Status.PUBLISHED,
            )
            self.category_a = DataCategory.objects.create(
                organization=self.org_a, name="Liên hệ giả lập", code="contact-demo"
            )
        with tenant_context(str(self.org_b.pk)):
            self.purpose_b = ProcessingPurpose.objects.create(
                organization=self.org_b, name="Mục đích tenant B", code="purpose-b"
            )

        rule = LegalRule.objects.create(
            code="dsar-response", title="DSAR demo", jurisdiction=LegalRule.Jurisdiction.VIETNAM_CURRENT
        )
        self.dsar_rule = RuleVersion.objects.create(
            legal_rule=rule,
            version="2026-test",
            effective_from=date(2026, 1, 1),
            duration_days=20,
        )

    def _create_case(self, *, request_type=DSARCase.RequestType.ERASURE, subject=None):
        return create_dsar_case(
            organization=self.org_a,
            subject_email=(subject or self.subject).email,
            subject_user=subject or self.subject,
            request_type=request_type,
            rule_version=self.dsar_rule,
            actor=subject or self.subject,
            requires_officer_approval=True,
        )

    def test_tenant_queryset_and_service_block_cross_tenant_record(self):
        with tenant_context(str(self.org_a.pk)):
            self.assertEqual(ProcessingPurpose.objects.count(), 1)
            self.assertFalse(ProcessingPurpose.objects.filter(pk=self.purpose_b.pk).exists())
            with self.assertRaises(PermissionDenied):
                record_consent(
                    organization=self.org_a,
                    subject_email=self.subject.email,
                    purpose=self.purpose_b,
                    notice_version=self.notice_a,
                    actor=self.subject,
                )

    def test_healthcheck_exposes_no_tenant_data(self):
        response = self.client.get(reverse("privacy:healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_consent_form_has_no_defaults_and_withdrawal_disables_purpose(self):
        field_name = ConsentSelectionForm.field_name_for(self.purpose_a.pk)
        blank_form = ConsentSelectionForm({"notice_acknowledged": "on"}, purposes=[self.purpose_a])
        self.assertFalse(blank_form.is_valid())
        self.assertFalse(blank_form.fields[field_name].initial)

        form = ConsentSelectionForm({"notice_acknowledged": "on", field_name: "on"}, purposes=[self.purpose_a])
        self.assertTrue(form.is_valid())
        event = record_consent(
            organization=self.org_a,
            subject_email=self.subject.email,
            purpose=self.purpose_a,
            notice_version=self.notice_a,
            actor=self.subject,
            evidence={"channel": "test"},
        )
        self.assertTrue(consent_is_active(organization=self.org_a, subject_email=self.subject.email, purpose=self.purpose_a))
        withdrawal = withdraw_consent(event=event, actor=self.subject, reason="test withdrawal")
        self.assertEqual(withdrawal.status, "withdrawn")
        self.assertFalse(consent_is_active(organization=self.org_a, subject_email=self.subject.email, purpose=self.purpose_a))

    def test_legal_hold_blocks_erasure_until_released(self):
        case = self._create_case()
        self.assertGreater(case.due_at, case.submitted_at)
        hold = create_legal_hold(organization=self.org_a, dsar_case=case, reason="Lưu giữ chứng cứ giả lập", actor=self.officer)
        approve_case(case=case, officer=self.officer)
        with self.assertRaises(WorkflowValidationError):
            complete_case(case=case, actor=self.officer)
        release_legal_hold(hold=hold, actor=self.officer, reason="Kết thúc hold giả lập")
        completed = complete_case(case=case, actor=self.officer)
        anonymised = anonymize_case(case=completed, actor=self.officer)
        self.assertEqual(anonymised.subject_email, "")
        self.assertIsNotNone(anonymised.anonymised_at)

    def test_transfer_and_incident_workflows_require_evidence_and_checklist(self):
        with tenant_context(str(self.org_a.pk)):
            vendor = Vendor.objects.create(organization=self.org_a, name="Cloud không đủ hồ sơ", country_code="US")
            transfer = Transfer.objects.create(
                organization=self.org_a,
                vendor=vendor,
                title="Transfer thiếu checklist",
                destination_country="US",
            )
            with self.assertRaises(ValidationError):
                mark_transfer_ready(transfer=transfer, actor=self.officer)

            incident = Incident.objects.create(
                organization=self.org_a,
                title="Incident giả lập",
                notification_due_at=timezone.now() + timedelta(hours=72),
            )
            with self.assertRaises(WorkflowValidationError):
                approve_incident(incident=incident, officer=self.officer)
            IncidentEvidence.objects.create(
                organization=self.org_a,
                incident=incident,
                title="Evidence giả lập",
                digest_sha256="1" * 64,
                collected_by=self.officer,
            )
            approved = approve_incident(incident=incident, officer=self.officer)
            reported = prepare_incident_notification(
                incident=approved,
                actor=self.officer,
                draft="Bản nháp học tập - không gửi cơ quan nhà nước.",
            )
        self.assertEqual(reported.status, Incident.Status.REPORTED)

    def test_export_expiry_and_subject_portal_access(self):
        case = self._create_case(request_type=DSARCase.RequestType.PORTABILITY)
        approve_case(case=case, officer=self.officer)
        with TemporaryDirectory() as export_root, override_settings(EXPORT_ROOT=export_root):
            artifact = create_export_artifact(case=case, format=ExportArtifact.Format.JSON, actor=self.subject)
            artifact = approve_export_artifact(artifact=artifact, officer=self.officer)
            artifact = generate_export_artifact(artifact=artifact, actor=self.officer)
            self.assertEqual(artifact.status, ExportArtifact.Status.READY)
            self.assertTrue((Path(export_root) / artifact.file_name).is_file())

            artifact.expires_at = timezone.now() - timedelta(seconds=1)
            artifact.save(update_fields=["expires_at", "updated_at"])
            session = self.client.session
            session["active_organization_id"] = str(self.org_a.pk)
            session.save()
            self.client.force_login(self.subject)
            response = self.client.get(reverse("privacy:export_download", args=[artifact.download_token]))
            self.assertEqual(response.status_code, 302)
            self.assertIn(reverse("privacy:dsar_detail", args=[case.reference]), response.url)

    def test_subject_cannot_open_another_subject_case(self):
        own_case = self._create_case(subject=self.subject)
        other_case = self._create_case(subject=self.other_subject)
        session = self.client.session
        session["active_organization_id"] = str(self.org_a.pk)
        session.save()
        self.client.force_login(self.subject)
        self.assertEqual(self.client.get(reverse("privacy:dsar_detail", args=[own_case.reference])).status_code, 200)
        self.assertEqual(self.client.get(reverse("privacy:dsar_detail", args=[other_case.reference])).status_code, 403)

    def test_privileged_compliance_workspace_requires_totp(self):
        self.client.force_login(self.officer)
        session = self.client.session
        session["active_organization_id"] = str(self.org_a.pk)
        session.save()

        response = self.client.get(reverse("privacy:compliance_dashboard"))
        self.assertRedirects(response, reverse("privacy:totp_setup"))
        self.client.get(reverse("privacy:totp_setup"))
        device = TOTPDevice.objects.get(user=self.officer, confirmed=False)
        token = str(totp(device.bin_key, step=device.step, t0=device.t0, digits=device.digits, drift=device.drift)).zfill(
            device.digits
        )
        response = self.client.post(reverse("privacy:totp_setup"), {"token": token})
        self.assertRedirects(response, reverse("privacy:dashboard"))
        self.assertTrue(TOTPDevice.objects.get(pk=device.pk).confirmed)
        self.assertEqual(self.client.get(reverse("privacy:compliance_dashboard")).status_code, 200)

    def test_deadline_worker_reestablishes_each_tenant_scope(self):
        case_a = self._create_case(request_type=DSARCase.RequestType.ACCESS)
        case_b = create_dsar_case(
            organization=self.org_b,
            subject_email="worker-b@example.test",
            request_type=DSARCase.RequestType.ACCESS,
            rule_version=self.dsar_rule,
            requires_officer_approval=False,
        )
        case_b.due_at = timezone.now() - timedelta(minutes=1)
        case_b.save(update_fields=["due_at", "updated_at"])

        counts = review_deadlines()
        case_a.refresh_from_db()
        case_b.refresh_from_db()
        self.assertGreaterEqual(counts["organizations"], 2)
        self.assertGreaterEqual(counts["overdue"], 1)
        self.assertEqual(case_a.sla_state, DSARCase.SlaState.ON_TRACK)
        self.assertEqual(case_b.sla_state, DSARCase.SlaState.OVERDUE)
