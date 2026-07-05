"""Builders that turn an operation into a balanced, unsaved :class:`Ecriture`.

Every builder validates its lines against the balance invariant before
returning; the caller owns the transaction (the entry is not persisted here).
"""

from datetime import date
from decimal import Decimal

from models import Ecriture, EcritureOrigine, LigneEcriture, SensCategorie

from .constants import CENTS, ZERO
from .invariants import EntryError, _as_amount, validate_lignes
from .tva import split_ttc


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
    tva_taux: Decimal | None = None,
    compte_tva_id: str | None = None,
) -> Ecriture:
    """Turn a plain recette/dépense into a balanced two- or three-line entry.

    * **Recette** — money in: D cash account / C produit account.
    * **Dépense** — money out: D charge account / C cash account.

    The category supplies the produit/charge account
    (``compte_categorie_id``); the cash account (``compte_tresorerie_id``,
    512/531) is the one the money actually moved on.

    When ``tva_taux`` is given and strictly positive, ``montant`` is read as a
    **TTC** amount: it is split into HT + VAT, the base line carries the HT and
    the rate/amount metadata, and a third line books the VAT on the same side as
    the category (VAT collectée credited on a recette, déductible debited on a
    dépense) against ``compte_tva_id``. Without a rate the entry stays two lines.

    The result is validated against the balance invariant before being returned
    (unsaved, so the caller owns the transaction).
    """
    montant = _as_amount(montant, "montant")
    if montant == ZERO:
        raise EntryError("Le montant doit être strictement positif.")

    base = montant
    tva_montant: Decimal | None = None
    if tva_taux is not None and tva_taux > ZERO:
        if compte_tva_id is None:
            raise EntryError("Un compte de TVA est requis pour appliquer un taux.")
        base, tva_montant = split_ttc(montant, tva_taux)

    tresorerie_line = LigneEcriture(compte_id=compte_tresorerie_id, libelle=libelle)
    base_line = LigneEcriture(compte_id=compte_categorie_id, libelle=libelle)
    tva_line = LigneEcriture(compte_id=compte_tva_id, libelle=libelle)
    if tva_montant is not None:
        base_line.tva_taux = tva_taux
        base_line.tva_montant = tva_montant

    if sens == SensCategorie.RECETTE:
        # Money in: D trésorerie TTC / C produit HT (+ C TVA collectée).
        tresorerie_line.debit = montant
        base_line.credit = base
        tva_line.credit = tva_montant
        lignes = [tresorerie_line, base_line]
        if tva_montant is not None:
            lignes.append(tva_line)
    else:
        # Money out: D charge HT (+ D TVA déductible) / C trésorerie TTC.
        base_line.debit = base
        tva_line.debit = tva_montant
        tresorerie_line.credit = montant
        lignes = [base_line]
        if tva_montant is not None:
            lignes.append(tva_line)
        lignes.append(tresorerie_line)
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
