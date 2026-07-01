"""V3 identity & access API: user accounts, associations, memberships.

Namespaced apart from the legacy association-login endpoints during the
strangler migration:

* ``/api/auth/*``           — user account & session.
* ``/api/asso/{id}/*``      — association-scoped access (URL scoping), guarded
                              by :func:`auth_context.get_active_membership`.

Historically a single ``routers/identity.py`` module, split by area (auth,
associations, members, invitations) over shared schemas/helpers. The aggregate
``router`` is re-exported so ``main.py``'s ``identity.router`` is unchanged.
"""

from fastapi import APIRouter

from .associations import router as _associations_router
from .auth import router as _auth_router
from .invitations import router as _invitations_router
from .members import router as _members_router

router = APIRouter()
router.include_router(_auth_router)
router.include_router(_associations_router)
router.include_router(_members_router)
router.include_router(_invitations_router)

__all__ = ["router"]
