"""Tenant-scoped persistence, reconciliation and matching for bank statements.

Every reference from the client (treasury account, statement line, entry) is
re-resolved against the active association here before use, and no query runs
without the ``association_id`` scope (plan §10). Entry creation from a line and
lettrage reuse the very same builder/resolution path as manual saisie, so there
is one accounting truth, not a parallel one.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from accounting_engine import next_numero_piece
from auth_context import AccessContext, owned_or_404
from banque import ParsedLigne
from models import (
    CategorieSaisie,
    Compte,
    Ecriture,
    ImportReleve,
    LigneBancaire,
    LigneBancaireStatut,
    LigneEcriture,
    RapprochementSuggestion,
    SensCategorie,
)
from routers.ecritures.builders import _build_simple_entry
from routers.ecritures.schemas import SaisieSimpleRequest
from routers.tresorerie.service import _owned_treasury

# Entries within this many days of a statement line are offered as matches.
_MATCH_WINDOW_DAYS = 30
_ZERO = Decimal("0")


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _conflict(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def owned_treasury(session: Session, association_id: str, compte_id: str) -> Compte:
    return _owned_treasury(session, association_id, compte_id)


def owned_ligne(session: Session, association_id: str, ligne_id: str) -> LigneBancaire:
    return owned_or_404(
        session, LigneBancaire, ligne_id, association_id, "Ligne bancaire introuvable"
    )


def owned_ecriture(session: Session, association_id: str, ecriture_id: str) -> Ecriture:
    return owned_or_404(
        session, Ecriture, ecriture_id, association_id, "Écriture introuvable"
    )


def owned_import(session: Session, association_id: str, import_id: str) -> ImportReleve:
    return owned_or_404(
        session, ImportReleve, import_id, association_id, "Import introuvable"
    )


def persist_import(
    session: Session,
    ctx: AccessContext,
    compte: Compte,
    filename: str,
    lignes: list[ParsedLigne],
) -> ImportReleve:
    """Stage an import batch and its statement lines (no commit).

    The parent ``ImportReleve`` is flushed before the child lines so Postgres
    never sees a child before its parent (FK ordering — a plain FK column does
    not order the unit-of-work flush).
    """
    releve = ImportReleve(
        association_id=ctx.association_id,
        compte_id=compte.id,
        filename=filename,
        nb_lignes=len(lignes),
        imported_by=ctx.user.id,
    )
    session.add(releve)
    session.flush()  # parent before children (Postgres FK ordering, cf. pitfalls)
    for pl in lignes:
        session.add(
            LigneBancaire(
                association_id=ctx.association_id,
                import_id=releve.id,
                compte_id=compte.id,
                date_operation=pl.date_operation,
                libelle=pl.libelle,
                montant=pl.montant,
            )
        )
    return releve


def _net_on_compte(
    session: Session, ecriture_id: str, compte_id: str
) -> Decimal | None:
    """Σ débit − Σ crédit of an entry on one account (None if it does not touch it)."""
    debit = func.coalesce(func.sum(LigneEcriture.debit), 0)
    credit = func.coalesce(func.sum(LigneEcriture.credit), 0)
    row = session.exec(
        select(debit, credit).where(
            LigneEcriture.ecriture_id == ecriture_id,
            LigneEcriture.compte_id == compte_id,
        )
    ).one()
    total = Decimal(str(row[0])) - Decimal(str(row[1]))
    # No line on this account → both sums are 0; distinguish "touches, nets to 0"
    # from "does not touch" by counting the lines.
    touches = session.exec(
        select(func.count())
        .select_from(LigneEcriture)
        .where(
            LigneEcriture.ecriture_id == ecriture_id,
            LigneEcriture.compte_id == compte_id,
        )
    ).one()
    return total if touches else None


def _linked_ecriture_ids(session: Session, association_id: str) -> set[str]:
    """Entry ids already lettré to a statement line (never double-reconcile)."""
    return {
        eid
        for eid in session.exec(
            select(LigneBancaire.ecriture_id).where(
                LigneBancaire.association_id == association_id,
                LigneBancaire.ecriture_id.is_not(None),
            )
        ).all()
        if eid is not None
    }


def suggestions(
    session: Session, ctx: AccessContext, ligne: LigneBancaire
) -> list[RapprochementSuggestion]:
    """Existing entries whose net on this account equals the line's signed amount.

    Restricted to a ±30-day window around the statement date, excluding entries
    already lettré, ordered by date proximity. All tenant-scoped.
    """
    linked = _linked_ecriture_ids(session, ctx.association_id)
    lo = ligne.date_operation - timedelta(days=_MATCH_WINDOW_DAYS)
    hi = ligne.date_operation + timedelta(days=_MATCH_WINDOW_DAYS)
    debit = func.coalesce(func.sum(LigneEcriture.debit), 0)
    credit = func.coalesce(func.sum(LigneEcriture.credit), 0)
    rows = session.exec(
        select(
            Ecriture.id,
            Ecriture.numero_piece,
            Ecriture.date,
            Ecriture.libelle,
            debit,
            credit,
        )
        .join(LigneEcriture, LigneEcriture.ecriture_id == Ecriture.id)
        .where(
            Ecriture.association_id == ctx.association_id,
            LigneEcriture.compte_id == ligne.compte_id,
            Ecriture.date >= lo,
            Ecriture.date <= hi,
        )
        .group_by(Ecriture.id, Ecriture.numero_piece, Ecriture.date, Ecriture.libelle)
    ).all()

    matches: list[RapprochementSuggestion] = []
    for eid, piece, jour, libelle, deb, cred in rows:
        if eid in linked:
            continue
        net = Decimal(str(deb)) - Decimal(str(cred))
        if net != ligne.montant:
            continue
        matches.append(
            RapprochementSuggestion(
                ecriture_id=eid,
                numero_piece=piece,
                date=jour,
                libelle=libelle,
                montant=net,
            )
        )
    matches.sort(key=lambda s: abs((s.date - ligne.date_operation).days))
    return matches[:10]


def rapprocher(
    session: Session, ctx: AccessContext, ligne: LigneBancaire, ecriture_id: str
) -> LigneBancaire:
    """Lettrer ``ligne`` to an existing entry that moves this treasury account."""
    if ligne.statut == LigneBancaireStatut.RAPPROCHE:
        raise _conflict("Ligne déjà rapprochée (délettrer d'abord).")
    ecriture = owned_ecriture(session, ctx.association_id, ecriture_id)
    if _net_on_compte(session, ecriture.id, ligne.compte_id) is None:
        raise _bad_request("L'écriture ne mouvemente pas ce compte de trésorerie.")

    other = session.exec(
        select(LigneBancaire.id).where(
            LigneBancaire.association_id == ctx.association_id,
            LigneBancaire.ecriture_id == ecriture.id,
            LigneBancaire.id != ligne.id,
        )
    ).first()
    if other is not None:
        raise _conflict("Cette écriture est déjà rapprochée à une autre ligne.")

    _mark_rapproche(ligne, ctx, ecriture.id)
    session.add(ligne)
    return ligne


def creer_ecriture(
    session: Session,
    ctx: AccessContext,
    ligne: LigneBancaire,
    categorie_id: str,
    *,
    evenement_id: str | None,
    tiers_id: str | None,
    reference_externe: str | None,
    mode_reglement,
) -> Ecriture:
    """Book an assisted entry from a statement line, then lettrer the line to it.

    The line's sign fixes the sens; the chosen category must match it. Reuses the
    manual simple-entry builder so the created entry is indistinguishable from a
    hand-typed one (same resolution, same balance validation).
    """
    if ligne.statut == LigneBancaireStatut.RAPPROCHE:
        raise _conflict("Ligne déjà rapprochée.")
    if ligne.montant == _ZERO:
        raise _bad_request("Montant nul : aucune écriture à créer.")

    categorie = session.exec(
        select(CategorieSaisie).where(
            CategorieSaisie.id == categorie_id,
            CategorieSaisie.association_id == ctx.association_id,
            CategorieSaisie.is_active.is_(True),
        )
    ).first()
    if categorie is None:
        raise _bad_request("Catégorie introuvable ou inactive.")

    implied = SensCategorie.RECETTE if ligne.montant > _ZERO else SensCategorie.DEPENSE
    if categorie.sens != implied:
        raise _bad_request(
            "La catégorie ne correspond pas au sens de l'opération "
            "(une entrée attend une recette, une sortie une dépense)."
        )

    body = SaisieSimpleRequest(
        categorie_id=categorie.id,
        compte_tresorerie_id=ligne.compte_id,
        montant=abs(ligne.montant),
        date=ligne.date_operation,
        libelle=ligne.libelle,
        tiers_id=tiers_id,
        evenement_id=evenement_id,
        reference_externe=reference_externe,
        mode_reglement=mode_reglement,
    )
    ecriture = _build_simple_entry(
        session, ctx, body, next_numero_piece(session, ctx.association_id)
    )
    session.add(ecriture)
    session.flush()  # obtain the id before lettrage
    _mark_rapproche(ligne, ctx, ecriture.id)
    session.add(ligne)
    return ecriture


def delettrer(
    session: Session, ctx: AccessContext, ligne: LigneBancaire
) -> LigneBancaire:
    """Undo a lettrage: the line returns to NON_RAPPROCHE, the entry is untouched."""
    if ligne.statut != LigneBancaireStatut.RAPPROCHE:
        raise _conflict("La ligne n'est pas rapprochée.")
    ligne.ecriture_id = None
    ligne.statut = LigneBancaireStatut.NON_RAPPROCHE
    ligne.rapproche_by = None
    ligne.rapproche_at = None
    session.add(ligne)
    return ligne


def ignorer(session: Session, ligne: LigneBancaire, ignore: bool) -> LigneBancaire:
    """Set aside a line (or bring it back), never a reconciled one."""
    if ligne.statut == LigneBancaireStatut.RAPPROCHE:
        raise _conflict("Ligne rapprochée : délettrer avant de l'ignorer.")
    ligne.statut = (
        LigneBancaireStatut.IGNORE if ignore else LigneBancaireStatut.NON_RAPPROCHE
    )
    session.add(ligne)
    return ligne


def _mark_rapproche(ligne: LigneBancaire, ctx: AccessContext, ecriture_id: str) -> None:
    ligne.ecriture_id = ecriture_id
    ligne.statut = LigneBancaireStatut.RAPPROCHE
    ligne.rapproche_by = ctx.user.id
    ligne.rapproche_at = datetime.now(UTC)
