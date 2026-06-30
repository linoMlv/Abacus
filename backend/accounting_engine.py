"""Double-entry engine: the invariants that keep every entry balanced.

This commit exposes the core balance invariant (Σ débit = Σ crédit). The
simple→double-entry posting engine and the gapless voucher numbering build on
this guarantee in later commits.

The invariant is intentionally pure (no I/O, no session): it can be unit-tested
in isolation and reused by every write path (simple entry, manual entry,
import, recurrence) so no entry can ever be persisted unbalanced.
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from sqlalchemy import func
from sqlmodel import Session, select

from models import (
    Association,
    Ecriture,
    EcritureOrigine,
    EcritureStatut,
    Exercice,
    ExerciceStatut,
    LigneEcriture,
    SensCategorie,
)

CENTS = Decimal("0.01")
ZERO = Decimal("0.00")


def validated_only():
    """SQL clause for official figures: validated entries only (drafts excluded).

    Every balance/report aggregation (trial balance, ledger, treasury soldes,
    synthesis, exports) filters on this so an unvalidated draft never inflates a
    reported figure. Opening-balance (à-nouveau) entries are validated on
    creation, so they always count. The journal *listing* stays a transparent
    register (it shows drafts with their statut) — only the figures exclude them.
    """
    return Ecriture.statut == EcritureStatut.VALIDEE


class EntryError(ValueError):
    """A double-entry invariant was violated. Message is user-facing (FR)."""


def validate_lignes(lignes: Sequence[LigneEcriture]) -> None:
    """Ensure ``lignes`` form a valid, balanced accounting entry.

    Rules enforced:

    * at least two lines (an entry moves value between accounts);
    * every line carries a non-negative amount on exactly one side
      (debit xor credit, strictly positive);
    * Σ débit = Σ crédit, and the total is strictly positive.

    Raises :class:`EntryError` (with a French message) on the first violation.
    """
    if len(lignes) < 2:
        raise EntryError("Une écriture comptable doit comporter au moins deux lignes.")

    total_debit = ZERO
    total_credit = ZERO
    for ligne in lignes:
        debit = _as_amount(ligne.debit, "débit")
        credit = _as_amount(ligne.credit, "crédit")
        if debit > ZERO and credit > ZERO:
            raise EntryError(
                "Une ligne ne peut porter à la fois un débit et un crédit."
            )
        if debit == ZERO and credit == ZERO:
            raise EntryError("Une ligne doit porter un montant au débit ou au crédit.")
        total_debit += debit
        total_credit += credit

    if total_debit != total_credit:
        raise EntryError(
            f"Écriture déséquilibrée : débit {total_debit} ≠ crédit {total_credit}."
        )
    if total_debit == ZERO:
        raise EntryError(
            "Le montant total de l'écriture doit être strictement positif."
        )


def _as_amount(value: Decimal | int | str, side: str) -> Decimal:
    """Coerce an amount to a non-negative 2-decimal :class:`Decimal`."""
    amount = Decimal(value).quantize(CENTS)
    if amount < ZERO:
        raise EntryError(f"Le montant au {side} ne peut pas être négatif.")
    return amount


def next_numero_piece(session: Session, association_id: str) -> int:
    """Return the next sequential voucher number for ``association_id``.

    Numbering is per association and continuous (``max + 1``). To avoid two
    concurrent writers picking the same number, the association row is locked
    ``FOR UPDATE`` first: the lock is held until the caller's transaction
    commits the new entry, serializing numbering per association. (The lock is a
    no-op on SQLite, which runs one writer at a time anyway; on PostgreSQL it is
    the real guard, backing up the ``(association_id, numero_piece)`` unique
    constraint.)
    """
    session.exec(
        select(Association.id).where(Association.id == association_id).with_for_update()
    ).first()
    current_max = session.exec(
        select(func.max(Ecriture.numero_piece)).where(
            Ecriture.association_id == association_id
        )
    ).one()
    return (current_max or 0) + 1


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


def build_ecriture_a_nouveau(
    *,
    association_id: str,
    exercice_id: str,
    journal_id: str,
    compte_tresorerie_id: str,
    compte_report_id: str,
    montant: Decimal | int | str,
    date_ecriture: date,
    libelle: str,
    numero_piece: int,
    created_by: str | None = None,
) -> Ecriture:
    """Opening balance of a treasury account as a balanced à-nouveau entry.

    A positive balance books D treasury / C report à nouveau (110); a negative
    balance (overdraft) reverses it. The result is validated against the balance
    invariant before being returned (unsaved — the caller owns the transaction).
    """
    montant = Decimal(montant).quantize(CENTS)
    if montant == ZERO:
        raise EntryError("Le solde initial doit être différent de zéro.")

    amount = abs(montant)
    if montant > ZERO:
        debit_compte, credit_compte = compte_tresorerie_id, compte_report_id
    else:
        debit_compte, credit_compte = compte_report_id, compte_tresorerie_id

    lignes = [
        LigneEcriture(compte_id=debit_compte, libelle=libelle, debit=amount),
        LigneEcriture(compte_id=credit_compte, libelle=libelle, credit=amount),
    ]
    validate_lignes(lignes)

    return Ecriture(
        association_id=association_id,
        exercice_id=exercice_id,
        journal_id=journal_id,
        date=date_ecriture,
        numero_piece=numero_piece,
        libelle=libelle,
        origine=EcritureOrigine.A_NOUVEAU,
        created_by=created_by,
        lignes=lignes,
    )


def build_ecriture_virement(
    *,
    association_id: str,
    exercice_id: str,
    journal_id: str,
    compte_source_id: str,
    compte_destination_id: str,
    montant: Decimal | int | str,
    date_ecriture: date,
    libelle: str,
    numero_piece: int,
    created_by: str | None = None,
) -> Ecriture:
    """Internal transfer between two treasury accounts as a balanced entry.

    Money leaves ``compte_source_id`` and lands on ``compte_destination_id``:
    D destination / C source (journal OD). The transfer nets to zero across the
    two accounts, so it never touches a charge/produit account and has no impact
    on the result. The result is validated against the balance invariant before
    being returned (unsaved — the caller owns the transaction).
    """
    if compte_source_id == compte_destination_id:
        raise EntryError(
            "La source et la destination du virement doivent être différentes."
        )
    montant = _as_amount(montant, "montant")
    if montant == ZERO:
        raise EntryError("Le montant doit être strictement positif.")

    lignes = [
        LigneEcriture(compte_id=compte_destination_id, libelle=libelle, debit=montant),
        LigneEcriture(compte_id=compte_source_id, libelle=libelle, credit=montant),
    ]
    validate_lignes(lignes)

    return Ecriture(
        association_id=association_id,
        exercice_id=exercice_id,
        journal_id=journal_id,
        date=date_ecriture,
        numero_piece=numero_piece,
        libelle=libelle,
        origine=EcritureOrigine.VIREMENT,
        created_by=created_by,
        lignes=lignes,
    )


def build_ecriture_extourne(
    *,
    original: Ecriture,
    numero_piece: int,
    date_ecriture: date | None = None,
    libelle: str | None = None,
    created_by: str | None = None,
) -> Ecriture:
    """Contre-passation of a posted entry: same lines with debit/credit swapped.

    The reversal nets the original to zero. It is returned unsaved as a *brouillon*
    (origine EXTOURNE, linked to the original via ``extourne_de_id``) for the caller
    to review and validate. Nothing is deleted — the original stays and the reversal
    takes its own voucher number, so numbering stays gapless (FEC, plan §10). Dated
    on the original's date by default, keeping the net effect within its period.
    """
    lignes = [
        LigneEcriture(
            compte_id=ligne.compte_id,
            libelle=ligne.libelle,
            debit=ligne.credit,
            credit=ligne.debit,
        )
        for ligne in original.lignes
    ]
    validate_lignes(lignes)

    return Ecriture(
        association_id=original.association_id,
        exercice_id=original.exercice_id,
        journal_id=original.journal_id,
        date=date_ecriture or original.date,
        numero_piece=numero_piece,
        libelle=(
            libelle or f"Extourne pièce n°{original.numero_piece} — {original.libelle}"
        ),
        origine=EcritureOrigine.EXTOURNE,
        extourne_de_id=original.id,
        # Carry the original's analytic tags so the reversal nets it out in
        # *every* dimension — not just the result-by-class, but the Synthèse
        # per-category / per-event breakdowns and the event "réalisé" too.
        categorie_id=original.categorie_id,
        evenement_id=original.evenement_id,
        tiers_id=original.tiers_id,
        reference_externe=original.reference_externe,
        mode_reglement=original.mode_reglement,
        created_by=created_by,
        lignes=lignes,
    )


def build_ecriture_simple(
    *,
    association_id: str,
    exercice_id: str,
    journal_id: str,
    compte_tresorerie_id: str,
    compte_categorie_id: str,
    sens: SensCategorie,
    montant: Decimal | int | str,
    date_ecriture: date,
    libelle: str,
    numero_piece: int,
    created_by: str | None = None,
    origine: EcritureOrigine = EcritureOrigine.SAISIE_SIMPLE,
) -> Ecriture:
    """Turn a plain recette/dépense into a balanced two-line entry.

    * **Recette** — money in: D cash account / C produit account.
    * **Dépense** — money out: D charge account / C cash account.

    The category supplies the produit/charge account
    (``compte_categorie_id``); the cash account (``compte_tresorerie_id``,
    512/531) is the one the money actually moved on. The result is validated
    against the balance invariant before being returned (unsaved, so the caller
    owns the transaction).
    """
    montant = _as_amount(montant, "montant")
    if montant == ZERO:
        raise EntryError("Le montant doit être strictement positif.")

    if sens == SensCategorie.RECETTE:
        debit_compte, credit_compte = compte_tresorerie_id, compte_categorie_id
    else:
        debit_compte, credit_compte = compte_categorie_id, compte_tresorerie_id

    lignes = [
        LigneEcriture(compte_id=debit_compte, libelle=libelle, debit=montant),
        LigneEcriture(compte_id=credit_compte, libelle=libelle, credit=montant),
    ]
    validate_lignes(lignes)

    return Ecriture(
        association_id=association_id,
        exercice_id=exercice_id,
        journal_id=journal_id,
        date=date_ecriture,
        numero_piece=numero_piece,
        libelle=libelle,
        origine=origine,
        created_by=created_by,
        lignes=lignes,
    )
