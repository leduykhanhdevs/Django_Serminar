"""Tenant context and PostgreSQL RLS session configuration."""

from __future__ import annotations

from django.db import connection, transaction

from .tenant_context import clear_current_organization, set_current_organization


class TenantContextMiddleware:
    """Bind the active membership to the request and DB transaction.

    The application role has no RLS bypass. PostgreSQL policies use
    ``app.current_organization_id`` set here; SQLite simply uses the app-level
    queryset filtering used by the local test suite.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        organization_id = request.session.get("active_organization_id") if request.user.is_authenticated else None
        request.organization_id = organization_id
        set_current_organization(organization_id)
        try:
            with transaction.atomic():
                if connection.vendor == "postgresql":
                    with connection.cursor() as cursor:
                        # A narrow self-select policy on Membership uses this
                        # setting to bootstrap the tenant picker.  It never
                        # permits writes without the organization policy.
                        cursor.execute(
                            "SELECT set_config('app.current_user_id', %s, true)",
                            [str(request.user.pk) if request.user.is_authenticated else ""],
                        )
                        cursor.execute(
                            "SELECT set_config('app.current_organization_id', %s, true)",
                            [str(organization_id or "")],
                        )

                # Do not trust a stale or tampered session value.  This check
                # intentionally uses all_objects: PostgreSQL RLS still limits
                # the lookup to the authenticated user's own memberships.
                if request.user.is_authenticated and organization_id:
                    from .models import Membership

                    is_active_member = Membership.all_objects.filter(
                        organization_id=organization_id,
                        user=request.user,
                        status=Membership.Status.ACTIVE,
                    ).exists()
                    if not is_active_member:
                        request.session.pop("active_organization_id", None)
                        organization_id = None
                        request.organization_id = None
                        set_current_organization(None)
                        if connection.vendor == "postgresql":
                            with connection.cursor() as cursor:
                                cursor.execute("SELECT set_config('app.current_organization_id', %s, true)", [""])
                return self.get_response(request)
        finally:
            clear_current_organization()
