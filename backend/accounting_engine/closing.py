"""Closing entries: result determination (solde cl.6/7 → 12) and the opening
report à nouveau of the next fiscal year (plan §6).
"""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from models import Ecriture, EcritureOrigine, LigneEcriture

from .constants import CENTS, ZERO
from .exercices import resultat_de_gestion
from .invariants import validate_lignes


def build_ecriture_determination_resultat(
    *,
    association_id: str,
    exercice_id: str,
    journal_id: str,
    soldes_gestion: Sequence[tuple[str, Decimal]],
    compte_excedent_id: str,
    compte_deficit_id: str,
    date_ecriture: date,
    numero_piece: int,
    libelle: str = "Détermination du résultat",
    created_by: str | None = None,
) -> Ecriture | None:
    """Closing entry that zeroes the class-6/7 accounts into the result account.

    Each charge (debit solde) is credited and each produit (credit solde) is
    debited by its solde; the balancing counterpart is the result: an excédent is
    credited to 120, a déficit debited to 129. Returns ``None`` when there is no
    gestion movement to close. Validated against the balance invariant before
    return (unsaved — the caller owns the transaction).
    """
    lignes: list[LigneEcriture] = []
    for compte_id, solde in soldes_gestion:
        solde = Decimal(solde).quantize(CENTS)
        if solde > ZERO:
            lignes.append(
                LigneEcriture(compte_id=compte_id, libelle=libelle, credit=solde)
            )
        elif solde < ZERO:
            lignes.append(
                LigneEcriture(compte_id=compte_id, libelle=libelle, debit=-solde)
            )
    if not lignes:
        return None

    resultat = resultat_de_gestion(soldes_gestion)
    if resultat > ZERO:
        lignes.append(
            LigneEcriture(
                compte_id=compte_excedent_id, libelle=libelle, credit=resultat
            )
        )
    elif resultat < ZERO:
        lignes.append(
            LigneEcriture(compte_id=compte_deficit_id, libelle=libelle, debit=-resultat)
        )
    validate_lignes(lignes)

    return Ecriture(
        association_id=association_id,
        exercice_id=exercice_id,
        journal_id=journal_id,
        date=date_ecriture,
        numero_piece=numero_piece,
        libelle=libelle,
        origine=EcritureOrigine.CLOTURE,
        created_by=created_by,
        lignes=lignes,
    )


def build_ecriture_report_a_nouveau(
    *,
    association_id: str,
    exercice_id: str,
    journal_id: str,
    soldes_bilan: Sequence[tuple[str, Decimal]],
    affectation_lignes: Sequence[tuple[str, Decimal, Decimal]],
    date_ecriture: date,
    numero_piece: int,
    libelle: str = "Report à nouveau",
    created_by: str | None = None,
) -> Ecriture | None:
    """Opening entry of the new fiscal year: carry balance-sheet accounts forward.

    ``soldes_bilan`` are the closing soldes of the class-1-5 accounts *excluding*
    the result account (12): a debit solde is carried as a debit, a credit solde
    as a credit. ``affectation_lignes`` post the result affectation directly
    (``(compte_id, débit, crédit)`` on 110/119/106) instead of carrying the 12
    account, which keeps the result out of the new year while preserving balance
    (the omitted 12 solde equals the affectation total). Returns ``None`` when
    there is nothing to carry. Validated against the balance invariant before
    return (unsaved — the caller owns the transaction).
    """
    lignes: list[LigneEcriture] = []
    for compte_id, solde in soldes_bilan:
        solde = Decimal(solde).quantize(CENTS)
        if solde > ZERO:
            lignes.append(
                LigneEcriture(compte_id=compte_id, libelle=libelle, debit=solde)
            )
        elif solde < ZERO:
            lignes.append(
                LigneEcriture(compte_id=compte_id, libelle=libelle, credit=-solde)
            )
    for compte_id, debit, credit in affectation_lignes:
        debit, credit = Decimal(debit).quantize(CENTS), Decimal(credit).quantize(CENTS)
        if debit > ZERO or credit > ZERO:
            lignes.append(
                LigneEcriture(
                    compte_id=compte_id, libelle=libelle, debit=debit, credit=credit
                )
            )
    if not lignes:
        return None
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
