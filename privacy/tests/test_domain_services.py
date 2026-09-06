from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from privacy.models import (
    AuditEvent,
    ConsentEvent,
    LegalRule,
    Membership,
    NoticeVersion,
    Organization,
    ProcessingPurpose,
    RuleVersion,
    AuditChainReport,
)
from privacy.services import (
    approve_case,
    consent_is_active,
    create_dsar_case,
    record_consent,
    restore_audit_event,
    simulate_audit_tampering,
    verify_audit_chain,
    withdraw_consent,
)
from privacy.tenant_context import tenant_context



class DomainServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.organization = Organization.objects.create(name="Demo Organization", slug="demo-org")
        self.subject = user_model.objects.create_user("subject", "subject@example.test", "test-password")
        self.officer = user_model.objects.create_user("officer", "officer@example.test", "test-password")
        Membership.all_objects.create(
            organization=self.organization,
            user=self.officer,
            role=Membership.Role.PRIVACY_OFFICER,
        )
        with tenant_context(str(self.organization.pk)):
            self.purpose = ProcessingPurpose.objects.create(organization=self.organization, name="Hỗ trợ", code="support")
            self.notice = NoticeVersion.objects.create(
                organization=self.organization,
                title="Thông báo privacy",
                version="1.0",
                body="Nội dung thông báo thử nghiệm.",
                status=NoticeVersion.Status.PUBLISHED,
            )
        rule = LegalRule.objects.create(code="dsar-response", title="DSAR", jurisdiction=LegalRule.Jurisdiction.VIETNAM_CURRENT)
        RuleVersion.objects.create(legal_rule=rule, version="2026.1", effective_from=date(2026, 1, 1), duration_days=30)

    def test_consent_withdrawal_and_hash_chain(self):
        with tenant_context(str(self.organization.pk)):
            event = record_consent(
                organization=self.organization,
                subject_email=self.subject.email,
                purpose=self.purpose,
                notice_version=self.notice,
                actor=self.subject,
            )
            self.assertEqual(event.status, ConsentEvent.Status.GRANTED)
            self.assertTrue(consent_is_active(organization=self.organization, subject_email=self.subject.email, purpose=self.purpose))
            withdrawal = withdraw_consent(event=event, actor=self.subject)
            self.assertEqual(withdrawal.status, ConsentEvent.Status.WITHDRAWN)
            self.assertFalse(consent_is_active(organization=self.organization, subject_email=self.subject.email, purpose=self.purpose))
            self.assertEqual(AuditEvent.objects.count(), 2)
            self.assertTrue(verify_audit_chain(organization=self.organization))

    def test_dsar_deadline_comes_from_rule_and_officer_approval(self):
        with tenant_context(str(self.organization.pk)):
            case = create_dsar_case(
                organization=self.organization,
                subject_email=self.subject.email,
                subject_user=self.subject,
                request_type="access",
                submitted_at=timezone.now(),
            )
            self.assertIsNotNone(case.due_at)
            approved = approve_case(case=case, officer=self.officer)
            self.assertEqual(approved.status, approved.Status.APPROVED)

    def test_audit_chain_verification_report_and_tamper_detection(self):
        with tenant_context(str(self.organization.pk)):
            # 1. Create a chain of audit events
            event = record_consent(
                organization=self.organization,
                subject_email=self.subject.email,
                purpose=self.purpose,
                notice_version=self.notice,
                actor=self.subject,
            )
            withdraw_consent(event=event, actor=self.subject)

            # 2. Test full report return
            report = verify_audit_chain(organization=self.organization, return_report=True)
            self.assertIsInstance(report, AuditChainReport)
            self.assertTrue(report.is_valid)
            self.assertEqual(report.total_events, 2)
            self.assertEqual(report.errors, [])
            self.assertGreaterEqual(report.duration_ms, 0)
            self.assertIsNone(report.tampered_sequence)

            # 3. Test backward compatible tuple unpacking
            valid, errors = verify_audit_chain(organization=self.organization, details=True)
            self.assertTrue(valid)
            self.assertEqual(errors, [])

            # 4. Test boolean casting
            self.assertTrue(verify_audit_chain(organization=self.organization))

            # 5. Simulate unauthorized tampering on sequence 1
            simulate_audit_tampering(
                organization=self.organization,
                sequence=1,
                tampered_metadata={"hacked": True},
            )

            # 6. Verify tampering detection
            tampered_report = verify_audit_chain(organization=self.organization, return_report=True)
            self.assertFalse(tampered_report.is_valid)
            self.assertEqual(tampered_report.tampered_sequence, 1)
            self.assertGreater(len(tampered_report.errors), 0)
            self.assertIn("Hash audit không hợp lệ tại sequence 1", tampered_report.errors[0])

            # 7. Restore and re-verify
            restore_audit_event(organization=self.organization, sequence=1)
            restored_report = verify_audit_chain(organization=self.organization, return_report=True)
            self.assertTrue(restored_report.is_valid)
            self.assertEqual(restored_report.errors, [])

