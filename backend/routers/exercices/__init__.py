"""Fiscal-year (exercice) lifecycle: listing, creation and closing.

Any active member may list the association's fiscal years (they are building
blocks of forms and reports). Opening a new year and closing one are structural
accounting acts, gated by :data:`Permission.EXERCISE_CLOSE`. Closing generates
the result-determination and report-à-nouveau entries and locks the year.

Split into closing helpers (``service.py``) and routes. The ``router`` is
re-exported so ``main.py``'s ``exercices.router`` is unchanged.
"""

from .routes import router

__all__ = ["router"]
