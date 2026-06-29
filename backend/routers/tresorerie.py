"""Treasury accounts: named class-5 accounts the treasurer follows (§15.4).

A treasury account is where the money is — bank, cash, online platform, savings.
It is a ``Compte`` of class 5 carrying a ``type_tresorerie``; its balance is never
stored but computed from the ledger. Creating one optionally posts an à-nouveau
entry for its opening balance. Every reference from the client is re-scoped to the
active association before use (``owned_or_404`` / explicit ``association_id`` filter).
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, SQLModel, asc, select

from accounting_engine import (
    CENTS,
    ZERO,
    EntryError,
    build_ecriture_a_nouveau,
    find_open_exercice,
    next_numero_piece,
)
from audit import AuditAction, record_audit
from auth_context import (
    AccessContext,
    get_active_membership,
    owned_or_404,
    require_permission,
)
from authz import Permission
from database import get_session
from models import (
    Compte,
    CompteTresorerieRead,
    CompteType,
    Ecriture,
    EcritureOrigine,
    EcritureStatut,
    Journal,
    LigneEcriture,
    TypeTresorerie,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["tresorerie"])

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


# --- Request schemas ------------------------------------------------------


class CreateTresorerieRequest(SQLModel):
    nom: str
    type_tresorerie: TypeTresorerie
    iban: str | None = None
    couleur: str | None = None
    solde_initial: Decimal | None = None
    date_solde_initial: date | None = None


class UpdateTresorerieRequest(SQLModel):
    nom: str | None = None
    type_tresorerie: TypeTresorerie | None = None
    iban: str | None = None
    couleur: str | None = None
    ordre: int | None = None
    is_active: bool | None = None


class SetSoldeInitialRequest(SQLModel):
    montant: Decimal  # 0 removes the opening balance
    date_solde_initial: date | None = None


# --- Helpers --------------------------------------------------------------


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
    """Current balance (Σ débit − Σ crédit) per account id, from the ledger."""
    if not compte_ids:
        return {}
    debit_sum = func.coalesce(func.sum(LigneEcriture.debit), 0)
    credit_sum = func.coalesce(func.sum(LigneEcriture.credit), 0)
    rows = session.exec(
        select(LigneEcriture.compte_id, debit_sum, credit_sum)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .where(
            Ecriture.association_id == association_id,
            LigneEcriture.compte_id.in_(compte_ids),
        )
        .group_by(LigneEcriture.compte_id)
    ).all()
    return {cid: Decimal(str(d)) - Decimal(str(c)) for cid, d, c in rows}


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
    session.add(ecriture)


# --- Endpoints ------------------------------------------------------------


@router.get("/tresorerie", response_model=list[CompteTresorerieRead])
def list_tresorerie(
    include_inactive: bool = False,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    """The association's treasury accounts with their current balances."""
    statement = select(Compte).where(
        Compte.association_id == ctx.association_id,
        Compte.type_tresorerie.is_not(None),
    )
    if not include_inactive:
        statement = statement.where(Compte.is_active.is_(True))
    comptes = session.exec(
        statement.order_by(asc(Compte.ordre), asc(Compte.numero))
    ).all()

    soldes = _treasury_soldes(session, ctx.association_id, [c.id for c in comptes])
    return [_to_read(c, soldes.get(c.id, ZERO)) for c in comptes]


@router.post(
    "/tresorerie",
    response_model=CompteTresorerieRead,
    status_code=status.HTTP_201_CREATED,
)
def create_tresorerie(
    body: CreateTresorerieRequest,
    ctx: AccessContext = Depends(require_permission(Permission.TRESORERIE_MANAGE)),
    session: Session = Depends(get_session),
):
    nom = body.nom.strip()
    if not nom:
        raise _bad_request("Le nom du compte est requis.")

    numero = _next_treasury_numero(
        session, ctx.association_id, _TYPE_PREFIX[body.type_tresorerie]
    )
    max_ordre = session.exec(
        select(func.coalesce(func.max(Compte.ordre), -1)).where(
            Compte.association_id == ctx.association_id,
            Compte.type_tresorerie.is_not(None),
        )
    ).one()

    compte = Compte(
        association_id=ctx.association_id,
        numero=numero,
        libelle=nom,
        classe=int(numero[0]),
        type=CompteType.ACTIF,
        type_tresorerie=body.type_tresorerie,
        iban=(body.iban or None),
        couleur=(body.couleur or None),
        ordre=max_ordre + 1,
    )
    session.add(compte)
    # Persist the account before the à-nouveau entry references it (FK ordering).
    session.flush()

    if body.solde_initial is not None and body.solde_initial != ZERO:
        jour = body.date_solde_initial or date.today()
        _post_solde_initial(session, ctx, compte, body.solde_initial, jour)

    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.COMPTE_TRESORERIE_CREATE,
        target_type="compte",
        target_id=compte.id,
        detail=f"{numero} {nom}",
    )
    session.commit()
    session.refresh(compte)

    solde = _treasury_soldes(session, ctx.association_id, [compte.id]).get(
        compte.id, ZERO
    )
    return _to_read(compte, solde)


@router.post(
    "/tresorerie/{compte_id}/solde-initial", response_model=CompteTresorerieRead
)
def set_solde_initial(
    compte_id: str,
    body: SetSoldeInitialRequest,
    ctx: AccessContext = Depends(require_permission(Permission.TRESORERIE_MANAGE)),
    session: Session = Depends(get_session),
):
    """Set (or remove, with 0) the opening balance of an existing treasury account.

    Useful at onboarding for the seeded Banque/Caisse. Replaces a previous *draft*
    à-nouveau entry; a *validated* opening balance is immutable (409 — a
    contre-passation is required). The opening balance posts D account / C report à
    nouveau (110); 0 simply removes the draft entry.
    """
    compte = _owned_treasury(session, ctx.association_id, compte_id)

    existing = _a_nouveau_entries(session, ctx.association_id, compte.id)
    if any(e.statut == EcritureStatut.VALIDEE for e in existing):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Le solde initial est validé et ne peut plus être modifié "
            "(contre-passation requise).",
        )
    for entry in existing:
        session.delete(entry)
    session.flush()  # apply the deletions before re-posting / renumbering

    montant = body.montant.quantize(CENTS)
    if montant != ZERO:
        jour = body.date_solde_initial or date.today()
        _post_solde_initial(session, ctx, compte, montant, jour)

    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.COMPTE_TRESORERIE_UPDATE,
        target_type="compte",
        target_id=compte.id,
        detail=f"solde initial {montant}",
    )
    session.commit()
    session.refresh(compte)

    solde = _treasury_soldes(session, ctx.association_id, [compte.id]).get(
        compte.id, ZERO
    )
    return _to_read(compte, solde)


@router.patch("/tresorerie/{compte_id}", response_model=CompteTresorerieRead)
def update_tresorerie(
    compte_id: str,
    body: UpdateTresorerieRequest,
    ctx: AccessContext = Depends(require_permission(Permission.TRESORERIE_MANAGE)),
    session: Session = Depends(get_session),
):
    """Rename / recolour / reorder / archive a treasury account.

    Archiving (``is_active = false``) never deletes: the ledger history stays
    valid. The account number is stable (kept for audit/FEC). ``iban``/``couleur``
    left out of the body are unchanged.
    """
    compte = _owned_treasury(session, ctx.association_id, compte_id)

    if body.nom is not None:
        nom = body.nom.strip()
        if not nom:
            raise _bad_request("Le nom du compte ne peut pas être vide.")
        compte.libelle = nom
    if body.type_tresorerie is not None:
        compte.type_tresorerie = body.type_tresorerie
    if body.iban is not None:
        compte.iban = body.iban or None
    if body.couleur is not None:
        compte.couleur = body.couleur or None
    if body.ordre is not None:
        compte.ordre = body.ordre
    if body.is_active is not None:
        compte.is_active = body.is_active

    session.add(compte)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.COMPTE_TRESORERIE_UPDATE,
        target_type="compte",
        target_id=compte.id,
        detail=f"{compte.numero} {compte.libelle}",
    )
    session.commit()
    session.refresh(compte)

    solde = _treasury_soldes(session, ctx.association_id, [compte.id]).get(
        compte.id, ZERO
    )
    return _to_read(compte, solde)
