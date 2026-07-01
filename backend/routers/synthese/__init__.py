"""Dashboard synthesis (T6): period analytics + current alerts in one read.

A single tenant-scoped, read-only endpoint that powers the Synthèse page:

* **résultat** of the period — produits (class 7) − charges (class 6),
* **répartition** of the period by category and by event,
* **courbe de trésorerie** — opening balance carried into the period, then the
  cumulative end-of-day balance of the treasury accounts (class 5 named),
* **alertes** — current state, independent of the period: drafts to validate,
  active events over their dépenses budget, and open fiscal years past due.

Reading is open to any active member; every aggregate is filtered on the
server-resolved ``association_id`` (an id from the client never widens access).
The computation lives in ``service.py``; the ``router`` is re-exported so
``main.py``'s ``synthese.router`` is unchanged.
"""

from .routes import router

__all__ = ["router"]
