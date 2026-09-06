"""Small request/task-local tenant context helper."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

_organization_id: ContextVar[str | None] = ContextVar("organization_id", default=None)


def get_current_organization_id() -> str | None:
    return _organization_id.get()


def set_current_organization(organization_id: str | None) -> None:
    _organization_id.set(str(organization_id) if organization_id else None)


def clear_current_organization() -> None:
    _organization_id.set(None)


@contextmanager
def tenant_context(organization_id: str):
    token = _organization_id.set(str(organization_id))
    try:
        yield
    finally:
        _organization_id.reset(token)

