"""Fiscal-year lookups and the management result, shared by write paths and
report scoping.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlmodel import Session, select

from models import Exercice, ExerciceStatut

from .constants import CENTS, ZERO


def find_open_exercice(
    session: Session, association_id: str, jour: date
) -> Exercice | None:
    """Return the *open* fiscal year of ``association_id`` covering ``jour``.

    Shared by every write path so an entry is always booked into a single open
    exercice derived from its date (never trusted from the client). Returns
    ``None`` when no open exercice covers the date — the caller maps that to a
    user-facing error.
    """
    return session.exec(
        select(Exercice).where(
            Exercice.association_id == association_id,
            Exercice.date_debut <= jour,
            Exercice.date_fin >= jour,
            Exercice.statut == ExerciceStatut.OUVERT,
        )
    ).first()


def find_exercice_covering(
    session: Session, association_id: str, jour: date
) -> Exercice | None:
    """Return the fiscal year of ``association_id`` covering ``jour`` (any statut).

    Unlike :func:`find_open_exercice` this ignores the statut: it answers "which
    exercice does this date belong to" for report scoping — balance-sheet figures
    are bounded below by the covering exercice's start, because its report à
    nouveau already sums up everything before it (plan §6). Periods never overlap
    (creation forbids it), so at most one exercice matches.
    """
    return session.exec(
        select(Exercice).where(
            Exercice.association_id == association_id,
            Exercice.date_debut <= jour,
            Exercice.date_fin >= jour,
        )
    ).first()


def scope_exercice(
    session: Session, association_id: str, jour: date
) -> Exercice | None:
    """Fiscal year a balance-sheet figure at ``jour`` must be scoped to.

    Balance-sheet figures (treasury soldes, bilan, annexe, ledger openings) are
    read within a single fiscal year, whose opening report à nouveau folds in
    everything before it (plan §6). That is the exercice covering ``jour``; when
    none covers it (a date past the last year, or a gap between years) fall back
    to the most recent exercice that has *started* on or before ``jour`` — **never**
    to an all-time sum, which would double-count a report à nouveau. Returns
    ``None`` only when no exercice has started yet (nothing to scope; there is no
    report à nouveau to double-count either).
    """
    covering = find_exercice_covering(session, association_id, jour)
    if covering is not None:
        return covering
    return session.exec(
        select(Exercice)
        .where(
            Exercice.association_id == association_id,
            Exercice.date_debut <= jour,
        )
        .order_by(Exercice.date_debut.desc())
    ).first()


def resultat_de_gestion(soldes_gestion: Sequence[tuple[str, Decimal]]) -> Decimal:
    """Net result from class-6/7 account soldes (``solde = Σdébit − Σcrédit``).

    Produits carry a credit balance (negative solde), charges a debit balance
    (positive solde); the result is produits − charges = −Σ soldes.
    """
    total = sum((Decimal(s) for _, s in soldes_gestion), ZERO)
    return (-total).quantize(CENTS)
