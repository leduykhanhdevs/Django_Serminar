from .tenant_context import get_current_organization_id


def privacy_context(request):
    return {"active_organization_id": get_current_organization_id()}
