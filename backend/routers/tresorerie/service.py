"""Treasury helpers: numbering, computed balances and the opening-balance entry.

Every reference from the client is re-scoped to the active association before
use (``owned_or_404`` / an explicit ``association_id`` filter).
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, select

from accounting_engine import (
    EntryError,
    build_ecriture_a_nouveau,
    find_open_exercice,
    next_numero_piece,
    scope_exercice,
    validated_only,
)
from auth_context import AccessContext, owned_or_404
from models import (
    Compte,
    CompteTresorerieRead,
    Ecriture,
    EcritureOrigine,
    EcritureStatut,
    Journal,
    LigneEcriture,
    TypeTresorerie,
)

# ANC account-number prefix per treasury type: physical cash -> 531, everything
# financial (bank, online, savings, other) -> 512 (cf. §15.4 "512/551").
_TYPE_PREFIX: dict[TypeTresorerie, str] = {
    TypeTresorerie.BANQUE: "512",
    TypeTresorerie.EN_LIGNE: "512",
    TypeTresorerie.EPARGNE: "512",
    TypeTresorerie.AUTRE: "512",
    TypeTresorerie.CAISSE: "531",
}

_REPORT_A_NOUVEAU_NUMERO = "110"  # contrepartie du solde initial
_JOURNAL_A_NOUVEAU = "OD"  # opérations diverses


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _next_treasury_numero(session: Session, association_id: str, prefix: str) -> str:
    """First free ``{prefix}{n}`` (n≥1) within the association's chart of accounts.

    The generic seeded number (e.g. "512") is already taken, so named accounts get
    readable sub-numbers (512 -> 5121, 5122…). The unique constraint backs this up.
    """
    taken = set(
        session.exec(
            select(Compte.numero).where(
                Compte.association_id == association_id,
                Compte.numero.startswith(prefix),
            )
        ).all()
    )
    n = 1
    while f"{prefix}{n}" in taken:
        n += 1
    return f"{prefix}{n}"


def _treasury_soldes(
    session: Session, association_id: str, compte_ids: list[str]
) -> dict[str, Decimal]:
    """Current balance (Σ débit − Σ crédit) per account id, from the ledger.

    Scoped to the exercice covering today (or, if none covers it, the most recent
    started one — see :func:`scope_exercice`): its report à nouveau already carries
    the opening balance forward, so counting prior years' movements too would
    double the opening once a year has been closed. Before any closing there is a
    single exercice covering everything — a no-op.
    """
    if not compte_ids:
        return {}
    current = scope_exercice(session, association_id, date.today())
    debit_sum = func.coalesce(func.sum(LigneEcriture.debit), 0)
    credit_sum = func.coalesce(func.sum(LigneEcriture.credit), 0)
    statement = (
        select(LigneEcriture.compte_id, debit_sum, credit_sum)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .where(
            Ecriture.association_id == association_id,
            LigneEcriture.compte_id.in_(compte_ids),
            validated_only(),
        )
        .group_by(LigneEcriture.compte_id)
    )
    if current is not None:
        statement = statement.where(Ecriture.exercice_id == current.id)
    return {
        cid: Decimal(str(d)) - Decimal(str(c))
        for cid, d, c in session.exec(statement).all()
    }


def _to_read(compte: Compte, solde: Decimal) -> CompteTresorerieRead:
    return CompteTresorerieRead(
        id=compte.id,
        numero=compte.numero,
        libelle=compte.libelle,
        type_tresorerie=compte.type_tresorerie,
        iban=compte.iban,
        couleur=compte.couleur,
        ordre=compte.ordre,
        is_active=compte.is_active,
        solde=solde,
    )


def _owned_treasury(session: Session, association_id: str, compte_id: str) -> Compte:
    compte = owned_or_404(
        session, Compte, compte_id, association_id, "Compte de trésorerie introuvable"
    )
    if compte.type_tresorerie is None:
        # Not a treasury account — reported as 404 (never reveal ordinary accounts).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Compte de trésorerie introuvable",
        )
    return compte


def _a_nouveau_entries(
    session: Session, association_id: str, compte_id: str
) -> list[Ecriture]:
    """Opening-balance (à-nouveau) entries touching ``compte_id``."""
    return list(
        session.exec(
            select(Ecriture).where(
                Ecriture.association_id == association_id,
                Ecriture.origine == EcritureOrigine.A_NOUVEAU,
                Ecriture.id.in_(
                    select(LigneEcriture.ecriture_id).where(
                        LigneEcriture.compte_id == compte_id
                    )
                ),
            )
        ).all()
    )


def _post_solde_initial(
    session: Session,
    ctx: AccessContext,
    compte: Compte,
    montant: Decimal,
    jour: date,
) -> None:
    """Stage the opening-balance à-nouveau entry for ``compte`` (no commit)."""
    exercice = find_open_exercice(session, ctx.association_id, jour)
    if exercice is None:
        raise _bad_request("Aucun exercice ouvert ne couvre la date du solde initial.")

    journal = session.exec(
        select(Journal).where(
            Journal.association_id == ctx.association_id,
            Journal.code == _JOURNAL_A_NOUVEAU,
        )
    ).first()
    report = session.exec(
        select(Compte).where(
            Compte.association_id == ctx.association_id,
            Compte.numero == _REPORT_A_NOUVEAU_NUMERO,
        )
    ).first()
    if journal is None or report is None:
        raise _bad_request("Référentiel comptable incomplet (journal OD / compte 110).")

    try:
        ecriture = build_ecriture_a_nouveau(
            association_id=ctx.association_id,
            exercice_id=exercice.id,
            journal_id=journal.id,
            compte_tresorerie_id=compte.id,
            compte_report_id=report.id,
            montant=montant,
            date_ecriture=jour,
            libelle=f"Solde initial — {compte.libelle}",
            numero_piece=next_numero_piece(session, ctx.association_id),
            created_by=ctx.user.id,
        )
    except EntryError as exc:
        raise _bad_request(str(exc))
    # An opening balance is a firm declaration of the starting position, not
    # pending work: it is validated on creation so it counts in the official
    # figures immediately (and becomes immutable — adjusted via contre-passation).
    ecriture.statut = EcritureStatut.VALIDEE
    ecriture.validated_by = ctx.user.id
    ecriture.validated_at = datetime.now(UTC)
    session.add(ecriture)
