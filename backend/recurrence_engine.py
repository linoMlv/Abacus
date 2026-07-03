"""Generate the entries a :class:`Recurrence` has fallen due for.

Idempotent by construction: each run books occurrences up to ``today`` and
advances ``prochaine_echeance`` past them, so running twice (the daily job *and*
a manual trigger) never duplicates one. Independent of any request context —
callable by the scheduler over every association.
"""

from calendar import monthrange
from datetime import UTC, date, datetime, timedelta

from sqlmodel import Session, select

from accounting_engine import (
    build_ecriture_simple,
    find_open_exercice,
    next_numero_piece,
)
from models import (
    CategorieSaisie,
    Compte,
    Ecriture,
    EcritureOrigine,
    EcritureStatut,
    Periodicite,
    Recurrence,
    RecurrenceMode,
)

_FINANCIAL_CLASS = 5
# Safety cap per recurrence per run: a template stuck far in the past can never
# spawn an unbounded number of entries in one pass.
_MAX_OCCURRENCES = 366


def add_months(day: date, months: int) -> date:
    """``day`` shifted by whole months, clamping to the target month's last day."""
    index = day.month - 1 + months
    year = day.year + index // 12
    month = index % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def next_echeance(day: date, periodicite: Periodicite) -> date:
    """The due date after ``day`` for a given periodicity."""
    if periodicite == Periodicite.HEBDOMADAIRE:
        return day + timedelta(days=7)
    if periodicite == Periodicite.MENSUELLE:
        return add_months(day, 1)
    if periodicite == Periodicite.TRIMESTRIELLE:
        return add_months(day, 3)
    return add_months(day, 12)  # ANNUELLE


def _build_occurrence(session: Session, rec: Recurrence, jour: date) -> Ecriture | None:
    """Build (unsaved) the simple entry a recurrence produces on ``jour``.

    Returns ``None`` when it cannot be posted (template's category/account
    archived, or no open exercice covers the date) — the caller then stops for
    this recurrence and retries on a later run.
    """
    categorie = session.exec(
        select(CategorieSaisie).where(
            CategorieSaisie.id == rec.categorie_id,
            CategorieSaisie.association_id == rec.association_id,
            CategorieSaisie.is_active.is_(True),
        )
    ).first()
    compte = session.exec(
        select(Compte).where(
            Compte.id == rec.compte_tresorerie_id,
            Compte.association_id == rec.association_id,
            Compte.is_active.is_(True),
        )
    ).first()
    if categorie is None or compte is None or compte.classe != _FINANCIAL_CLASS:
        return None

    exercice = find_open_exercice(session, rec.association_id, jour)
    if exercice is None:
        return None

    ecriture = build_ecriture_simple(
        association_id=rec.association_id,
        exercice_id=exercice.id,
        journal_id=categorie.journal_id,
        compte_tresorerie_id=compte.id,
        compte_categorie_id=categorie.compte_id,
        sens=categorie.sens,
        montant=rec.montant,
        date_ecriture=jour,
        libelle=rec.libelle,
        numero_piece=next_numero_piece(session, rec.association_id),
        created_by=rec.created_by,
        origine=EcritureOrigine.RECURRENCE,
    )
    ecriture.categorie_id = categorie.id
    ecriture.tiers_id = rec.tiers_id
    ecriture.evenement_id = rec.evenement_id
    ecriture.reference_externe = rec.reference_externe
    ecriture.mode_reglement = rec.mode_reglement
    ecriture.recurrence_id = rec.id
    # Auto mode books a firm entry (validated, so it counts at once and is then
    # immutable). Proposition mode leaves a draft for the treasurer to review.
    if rec.mode == RecurrenceMode.AUTO:
        ecriture.statut = EcritureStatut.VALIDEE
        ecriture.validated_by = rec.created_by
        ecriture.validated_at = datetime.now(UTC)
    return ecriture


def generate_due(
    session: Session,
    *,
    today: date | None = None,
    association_id: str | None = None,
) -> int:
    """Book every occurrence due on or before ``today``; return how many.

    Scoped to one association or, by default, all of them (the daily job). Does
    not commit — the caller owns the transaction.
    """
    today = today or date.today()
    statement = select(Recurrence).where(
        Recurrence.actif.is_(True),
        Recurrence.prochaine_echeance <= today,
    )
    if association_id is not None:
        statement = statement.where(Recurrence.association_id == association_id)

    generated = 0
    for rec in session.exec(statement).all():
        occurrences = 0
        while (
            rec.prochaine_echeance <= today
            and (rec.date_fin is None or rec.prochaine_echeance <= rec.date_fin)
            and occurrences < _MAX_OCCURRENCES
        ):
            jour = rec.prochaine_echeance
            ecriture = _build_occurrence(session, rec, jour)
            if ecriture is None:
                break  # cannot post now — leave prochaine_echeance, retry later
            session.add(ecriture)
            rec.derniere_generation = jour
            rec.prochaine_echeance = next_echeance(jour, rec.periodicite)
            session.add(rec)
            # Flush so the next voucher number sees this just-added entry.
            session.flush()
            generated += 1
            occurrences += 1
        # A recurrence whose end date has passed is done: switch it off.
        if rec.date_fin is not None and rec.prochaine_echeance > rec.date_fin:
            rec.actif = False
            session.add(rec)
    return generated
