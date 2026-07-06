"""Fiscal-year budget (Phase 5): prévu per category vs réalisé from the ledger.

A budget is one prévu amount per plain-language category for an exercice; the
réalisé is recomputed from the validated ledger (never stored). Reading returns
the full grid (every active category with prévu/réalisé/écart) plus per-sens
totals and the prévisionnel/réalisé results; upsert replaces the grid. Both are
gated by ``BUDGET_MANAGE`` and scoped to the active association. The computation
lives in ``service.py`` over :mod:`budget_engine`; the ``router`` is re-exported
so ``main.py`` stays unchanged.
"""

from .routes import router

__all__ = ["router"]
