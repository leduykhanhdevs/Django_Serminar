"""Direct database proof for PostgreSQL tenant RLS.

The class is skipped on SQLite so contributors can run the ordinary local test
suite.  The test runner creates the database as the migration owner, then
explicitly assumes the non-bypass application role before evaluating a policy.
"""

from __future__ import annotations

import os
from unittest import skipUnless

from django.db import DatabaseError, connection, transaction
from django.test import TestCase

from privacy.models import Organization, ProcessingPurpose


@skipUnless(connection.vendor == "postgresql", "Requires PostgreSQL RLS")
class PostgreSQLRLSTests(TestCase):
    def setUp(self):
        self.org_a = Organization.objects.create(name="RLS A", slug="rls-a")
        self.org_b = Organization.objects.create(name="RLS B", slug="rls-b")
        self._set_tenant(self.org_a)
        ProcessingPurpose.all_objects.create(organization=self.org_a, name="A only", code="a-only")
        self._set_tenant(self.org_b)
        ProcessingPurpose.all_objects.create(organization=self.org_b, name="B only", code="b-only")
        self._grant_application_role_test_access()

    @property
    def application_role(self) -> str:
        return os.getenv("POSTGRES_APP_USER", "privacyhub_app")

    def _grant_application_role_test_access(self) -> None:
        """Give the application role normal table privileges in the transient DB.

        The test database is created after the normal Compose bootstrap, so it
        does not inherit the production database's explicit grants.  These
        grants deliberately do not grant ownership or BYPASSRLS.
        """
        quoted_role = connection.ops.quote_name(self.application_role)
        with connection.cursor() as cursor:
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted_role}")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quoted_role}"
            )
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted_role}")

    def _assume_application_role(self) -> None:
        quoted_role = connection.ops.quote_name(self.application_role)
        with connection.cursor() as cursor:
            # SET LOCAL is scoped to Django TestCase's transaction and resets
            # automatically at teardown; a superuser must not test RLS as itself.
            cursor.execute(f"SET LOCAL ROLE {quoted_role}")
            cursor.execute("SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user")
            self.assertFalse(cursor.fetchone()[0], "RLS test must use a role without BYPASSRLS")

    @staticmethod
    def _set_tenant(organization):
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_organization_id', %s, true)", [str(organization.pk)])

    def test_direct_reads_and_cross_tenant_writes_are_blocked(self):
        self._assume_application_role()
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('app.current_organization_id', %s, true)", [""])
            cursor.execute("SELECT COUNT(*) FROM privacy_processingpurpose")
            self.assertEqual(cursor.fetchone()[0], 0)

        self._set_tenant(self.org_a)
        with connection.cursor() as cursor:
            cursor.execute("SELECT code FROM privacy_processingpurpose ORDER BY code")
            self.assertEqual([row[0] for row in cursor.fetchall()], ["a-only"])

        with transaction.atomic():
            with self.assertRaises(DatabaseError):
                ProcessingPurpose.all_objects.create(
                    organization=self.org_b,
                    name="blocked cross-tenant write",
                    code="blocked-write",
                )
