"""Enable PostgreSQL RLS for every operational tenant table.

SQLite remains supported for local seminar tests.  PostgreSQL uses the request
or worker transaction-local setting established by TenantContextMiddleware and
privacy.services.organization_scope.
"""

from django.db import migrations


TENANT_TABLES = (
    "privacy_legalentity",
    "privacy_membership",
    "privacy_processingpurpose",
    "privacy_datacategory",
    "privacy_processingactivity",
    "privacy_processingactivitypurpose",
    "privacy_processingactivitydatacategory",
    "privacy_roleassignment",
    "privacy_noticeversion",
    "privacy_noticepurpose",
    "privacy_consentevent",
    "privacy_dsarcase",
    "privacy_dsarcasetask",
    "privacy_legalhold",
    "privacy_retentionpolicy",
    "privacy_vendor",
    "privacy_subprocessor",
    "privacy_impactdossier",
    "privacy_exemptionassessment",
    "privacy_transfer",
    "privacy_transferdatacategory",
    "privacy_incident",
    "privacy_incidentevidence",
    "privacy_exportartifact",
    "privacy_auditevent",
)

POLICY_NAME = "privacy_tenant_isolation"
MEMBERSHIP_BOOTSTRAP_POLICY = "privacy_membership_self_select"


def enable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        for table in TENANT_TABLES:
            quoted_table = quote(table)
            quoted_policy = quote(POLICY_NAME)
            cursor.execute(f"ALTER TABLE {quoted_table} ENABLE ROW LEVEL SECURITY")
            cursor.execute(f"ALTER TABLE {quoted_table} FORCE ROW LEVEL SECURITY")
            cursor.execute(f"DROP POLICY IF EXISTS {quoted_policy} ON {quoted_table}")
            cursor.execute(
                f"""
                CREATE POLICY {quoted_policy} ON {quoted_table}
                USING (organization_id::text = NULLIF(current_setting('app.current_organization_id', true), ''))
                WITH CHECK (organization_id::text = NULLIF(current_setting('app.current_organization_id', true), ''))
                """
            )
        # Before a user selects a tenant, the portal must be able to read only
        # that user's memberships.  It is deliberately SELECT-only; writes
        # still require the organization policy above.
        membership_table = quote("privacy_membership")
        membership_policy = quote(MEMBERSHIP_BOOTSTRAP_POLICY)
        cursor.execute(f"DROP POLICY IF EXISTS {membership_policy} ON {membership_table}")
        cursor.execute(
            f"""
            CREATE POLICY {membership_policy} ON {membership_table} FOR SELECT
            USING (user_id::text = NULLIF(current_setting('app.current_user_id', true), ''))
            """
        )


def disable_rls(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    quote = schema_editor.quote_name
    with schema_editor.connection.cursor() as cursor:
        membership_table = quote("privacy_membership")
        membership_policy = quote(MEMBERSHIP_BOOTSTRAP_POLICY)
        cursor.execute(f"DROP POLICY IF EXISTS {membership_policy} ON {membership_table}")
        for table in TENANT_TABLES:
            quoted_table = quote(table)
            quoted_policy = quote(POLICY_NAME)
            cursor.execute(f"DROP POLICY IF EXISTS {quoted_policy} ON {quoted_table}")
            cursor.execute(f"ALTER TABLE {quoted_table} NO FORCE ROW LEVEL SECURITY")
            cursor.execute(f"ALTER TABLE {quoted_table} DISABLE ROW LEVEL SECURITY")


class Migration(migrations.Migration):
    dependencies = [("privacy", "0001_initial")]

    operations = [migrations.RunPython(enable_rls, disable_rls)]
