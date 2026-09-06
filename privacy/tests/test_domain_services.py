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
)
from privacy.services import (
    approve_case,
    consent_is_active,
    create_dsar_case,
    record_consent,
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
