"""Accounting entries: assisted (simple) and manual creation, read, validation.

Every reference coming from the client (category, account, journal, entry id) is
re-resolved against the active association before use — an id is never trusted
to authorize access. Validated entries are immutable and entries can only be
booked into an *open* fiscal year covering their date.

Historically a single ``routers/ecritures.py`` module, split into schemas,
tenant-scoped resolution helpers, entry builders and routes. The ``router`` is
re-exported so ``main.py``'s ``ecritures.router`` is unchanged.
"""

from .routes import router

__all__ = ["router"]
