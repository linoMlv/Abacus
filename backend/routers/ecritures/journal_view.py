"""Build the journal rows the two views read (C24).

One listing serves both the plain-language view (what happened to the money, on
which account) and the accountant's view (débit/crédit, counterparts). Everything
either view needs is derived here, server-side, from the entries already loaded
with their lines — three small lookups for the tenant's journals, accounts and
categories, and no per-row query.
"""

from decimal import Decimal

from sqlmodel import Session, select

from accounting_engine import CLASSE_TRESORERIE, ZERO
from models import (
    CategorieSaisie,
    Compte,
    Ecriture,
    EcritureListItem,
    EcritureOrigine,
    Journal,
    LigneEcriture,
    LigneJournalRead,
    SensCategorie,
)

# The three type-first words a treasurer reasons with (§15.3).
SENS_RECETTE = "recette"
SENS_DEPENSE = "depense"
SENS_VIREMENT = "virement"


def _is_treasury(compte: Compte | None) -> bool:
    return compte is not None and compte.classe == CLASSE_TRESORERIE


def _sens(ecriture: Ecriture, categorie_sens: SensCategorie | None) -> str | None:
    """Recette / dépense / virement — or nothing, rather than a guess.

    Mirrors what the journal *filters* on, deliberately: virement comes from the
    origine, recette/dépense from the category's sens. A manual entry carries no
    category and claims no direction. A contre-passation keeps its original's
    category (so it nets it out everywhere) and therefore reads with the same sens;
    what tells the reader it *removed* money is the signed treasury movement below,
    not a different word.
    """
    if ecriture.origine is EcritureOrigine.VIREMENT:
        return SENS_VIREMENT
    if categorie_sens is SensCategorie.RECETTE:
        return SENS_RECETTE
    if categorie_sens is SensCategorie.DEPENSE:
        return SENS_DEPENSE
    return None


def _treasury_view(
    lignes: list[LigneEcriture], comptes: dict[str, Compte], is_virement: bool
) -> tuple[str | None, str | None, Decimal | None]:
    """(compte, contrepartie, mouvement signé) as seen from treasury.

    For a virement, both ends are named — source (credited) then destination
    (debited) — and the signed movement is meaningless (money only moved inside),
    so it stays None. Otherwise the single treasury account is named and the
    movement is signed: positive = money in, negative = money out.
    """
    treasury = [ligne for ligne in lignes if _is_treasury(comptes.get(ligne.compte_id))]
    if not treasury:
        return None, None, None

    if is_virement:
        source = next((ligne for ligne in treasury if ligne.credit > 0), None)
        destination = next((ligne for ligne in treasury if ligne.debit > 0), None)
        return (
            comptes[source.compte_id].libelle if source else None,
            comptes[destination.compte_id].libelle if destination else None,
            None,
        )

    mouvement = sum((ligne.debit - ligne.credit for ligne in treasury), ZERO)
    return comptes[treasury[0].compte_id].libelle, None, mouvement


def build_journal_rows(
    session: Session, association_id: str, ecritures: list[Ecriture]
) -> list[EcritureListItem]:
    """Turn loaded entries into journal rows, ready for both views."""
    if not ecritures:
        return []

    journal_codes = {
        j.id: j.code
        for j in session.exec(
            select(Journal).where(Journal.association_id == association_id)
        ).all()
    }
    comptes = {
        c.id: c
        for c in session.exec(
            select(Compte).where(Compte.association_id == association_id)
        ).all()
    }
    categorie_sens = {
        c.id: c.sens
        for c in session.exec(
            select(CategorieSaisie).where(
                CategorieSaisie.association_id == association_id
            )
        ).all()
    }

    rows: list[EcritureListItem] = []
    for e in ecritures:
        sens = _sens(e, categorie_sens.get(e.categorie_id))
        compte, contrepartie, mouvement = _treasury_view(
            list(e.lignes), comptes, sens == SENS_VIREMENT
        )
        rows.append(
            EcritureListItem(
                id=e.id,
                exercice_id=e.exercice_id,
                journal_id=e.journal_id,
                categorie_id=e.categorie_id,
                date=e.date,
                numero_piece=e.numero_piece,
                libelle=e.libelle,
                tiers_id=e.tiers_id,
                evenement_id=e.evenement_id,
                reference_externe=e.reference_externe,
                mode_reglement=e.mode_reglement,
                statut=e.statut,
                origine=e.origine,
                extourne_de_id=e.extourne_de_id,
                recurrence_id=e.recurrence_id,
                created_at=e.created_at,
                validated_at=e.validated_at,
                montant=sum((ligne.debit for ligne in e.lignes), ZERO),
                journal_code=journal_codes.get(e.journal_id, ""),
                sens=sens,
                compte_libelle=compte,
                compte_contrepartie_libelle=contrepartie,
                montant_tresorerie=mouvement,
                lignes=[
                    LigneJournalRead(
                        compte_id=ligne.compte_id,
                        compte_numero=comptes[ligne.compte_id].numero
                        if ligne.compte_id in comptes
                        else "",
                        compte_libelle=comptes[ligne.compte_id].libelle
                        if ligne.compte_id in comptes
                        else "",
                        libelle=ligne.libelle,
                        debit=ligne.debit,
                        credit=ligne.credit,
                    )
                    for ligne in e.lignes
                ],
            )
        )
    return rows
