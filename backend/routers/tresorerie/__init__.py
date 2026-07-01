"""Treasury accounts: named class-5 accounts the treasurer follows (§15.4).

A treasury account is where the money is — bank, cash, online platform, savings.
It is a ``Compte`` of class 5 carrying a ``type_tresorerie``; its balance is never
stored but computed from the ledger. Creating one optionally posts an à-nouveau
entry for its opening balance.

Split into schemas, service helpers (numbering/balances/opening entry) and
routes. The ``router`` is re-exported so ``main.py``'s ``tresorerie.router`` is
unchanged.
"""

from .routes import router

__all__ = ["router"]
