"""Donation tax receipts (reçus fiscaux, art. 200/238 bis CGI, §8).

A *don* is an ordinary validated recette entry attached to a donor tiers — no
parallel ledger. A :class:`RecuFiscal` is the legal document issued for one or
several such dons of the same donor (per-don or annual cumulative); each don can
appear on at most one receipt (enforced by a unique link), so a donation is never
receipted twice. Every read/write is tenant-scoped; issuing/deleting is gated by
``DONATION_MANAGE``.
"""

from datetime import date
from decimal import Decimal
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import aliased
from sqlmodel import Session, select

from accounting_engine import validated_only
from audit import AuditAction, record_audit
from auth_context import (
    AccessContext,
    owned_or_404,
    require_permission,
)
from authz import Permission
from database import get_session
from exports import documents
from http_errors import bad_request as _bad_request
from models import (
    Association,
    CategorieSaisie,
    DonRead,
    Ecriture,
    EcritureOrigine,
    EcritureStatut,
    FormeDon,
    LigneEcriture,
    ModeReglement,
    RecuFiscal,
    RecuFiscalLigne,
    RecuFiscalRead,
    SensCategorie,
    Tiers,
    TypeTiers,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["dons"])


class CreerRecuRequest(BaseModel):
    tiers_id: str
    ecriture_ids: list[str]
    date: date
    annee: int
    forme: FormeDon = FormeDon.NUMERAIRE
    mode_reglement: ModeReglement | None = None


def _eligible_dons(
    session: Session,
    association_id: str,
    *,
    annee: int | None = None,
    tiers_id: str | None = None,
    only_unreceipted: bool = False,
) -> list[DonRead]:
    """Live donation recettes attached to a donor tiers, with receipt status.

    A single query: total = Σ debit of the entry, left-joined to the receipt link
    so an already-receipted don carries its receipt number. Only genuine, live
    donations qualify — reversal (extourne) entries are never dons, and an entry
    that has been contre-passée (a validated extourne points at it) is netted to
    zero and excluded, so a cancelled donation is neither offered nor receipted.
    """
    reversal = aliased(Ecriture)
    reversed_ids = select(reversal.extourne_de_id).where(
        reversal.association_id == association_id,
        reversal.origine == EcritureOrigine.EXTOURNE,
        reversal.statut == EcritureStatut.VALIDEE,
        reversal.extourne_de_id.is_not(None),
    )
    montant = func.coalesce(func.sum(LigneEcriture.debit), 0)
    statement = (
        select(
            Ecriture.id,
            Ecriture.date,
            Ecriture.numero_piece,
            Ecriture.libelle,
            Ecriture.tiers_id,
            Tiers.nom,
            RecuFiscal.id,
            RecuFiscal.numero,
            montant,
        )
        .join(Tiers, Tiers.id == Ecriture.tiers_id)
        .join(CategorieSaisie, CategorieSaisie.id == Ecriture.categorie_id)
        .join(LigneEcriture, LigneEcriture.ecriture_id == Ecriture.id)
        .outerjoin(RecuFiscalLigne, RecuFiscalLigne.ecriture_id == Ecriture.id)
        .outerjoin(RecuFiscal, RecuFiscal.id == RecuFiscalLigne.recu_fiscal_id)
        .where(
            Ecriture.association_id == association_id,
            Tiers.type == TypeTiers.DONATEUR,
            CategorieSaisie.sens == SensCategorie.RECETTE,
            Ecriture.origine != EcritureOrigine.EXTOURNE,
            Ecriture.id.not_in(reversed_ids),
            validated_only(),
        )
        .group_by(
            Ecriture.id,
            Ecriture.date,
            Ecriture.numero_piece,
            Ecriture.libelle,
            Ecriture.tiers_id,
            Tiers.nom,
            RecuFiscal.id,
            RecuFiscal.numero,
        )
        .order_by(Ecriture.date.desc(), Ecriture.numero_piece.desc())
    )
    if annee is not None:
        statement = statement.where(
            Ecriture.date >= date(annee, 1, 1),
            Ecriture.date <= date(annee, 12, 31),
        )
    if tiers_id is not None:
        statement = statement.where(Ecriture.tiers_id == tiers_id)
    if only_unreceipted:
        statement = statement.where(RecuFiscal.id.is_(None))

    rows = session.exec(statement).all()
    return [
        DonRead(
            ecriture_id=eid,
            date=d,
            numero_piece=piece,
            libelle=libelle,
            montant=Decimal(str(total)),
            tiers_id=tid,
            tiers_nom=nom,
            recu_id=recu_id,
            recu_numero=recu_numero,
        )
        for eid, d, piece, libelle, tid, nom, recu_id, recu_numero, total in rows
    ]


def _next_numero(session: Session, association_id: str) -> int:
    """Next sequential receipt number for the association (locked, gapless)."""
    session.exec(
        select(Association.id).where(Association.id == association_id).with_for_update()
    ).first()
    current_max = session.exec(
        select(func.max(RecuFiscal.numero)).where(
            RecuFiscal.association_id == association_id
        )
    ).one()
    return (current_max or 0) + 1


def _require_fiscal_identity(association: Association) -> None:
    missing = [
        label
        for field, label in (
            ("adresse", "adresse"),
            ("code_postal", "code postal"),
            ("ville", "ville"),
        )
        if not getattr(association, field)
    ]
    if not (association.rna or association.siret):
        missing.append("RNA ou SIRET")
    if missing:
        raise _bad_request(
            "Identité fiscale de l'association incomplète (Paramètres → "
            f"Comptabilité) : {', '.join(missing)}."
        )


def _require_donor_address(tiers: Tiers) -> None:
    if not (tiers.adresse and tiers.code_postal and tiers.ville):
        raise _bad_request(
            f"Adresse du donateur « {tiers.nom} » incomplète (nom, adresse, "
            "code postal et ville sont requis sur le reçu)."
        )


def _to_read(recu: RecuFiscal, tiers_nom: str) -> RecuFiscalRead:
    return RecuFiscalRead(
        id=recu.id,
        numero=recu.numero,
        tiers_id=recu.tiers_id,
        tiers_nom=tiers_nom,
        date=recu.date,
        annee=recu.annee,
        montant=recu.montant,
        forme=recu.forme,
        mode_reglement=recu.mode_reglement,
        annule=recu.annule,
    )


@router.get("/dons", response_model=list[DonRead])
def list_dons(
    annee: int | None = None,
    non_recu: bool = False,
    ctx: AccessContext = Depends(require_permission(Permission.DONATION_MANAGE)),
    session: Session = Depends(get_session),
):
    """Donations eligible for a receipt (validated recettes with a donor)."""
    return _eligible_dons(
        session, ctx.association_id, annee=annee, only_unreceipted=non_recu
    )


@router.get("/recus", response_model=list[RecuFiscalRead])
def list_recus(
    ctx: AccessContext = Depends(require_permission(Permission.DONATION_MANAGE)),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(RecuFiscal, Tiers.nom)
        .join(Tiers, Tiers.id == RecuFiscal.tiers_id)
        .where(RecuFiscal.association_id == ctx.association_id)
        .order_by(RecuFiscal.numero.desc())
    ).all()
    return [_to_read(recu, nom) for recu, nom in rows]


@router.post("/recus", response_model=RecuFiscalRead, status_code=201)
def creer_recu(
    body: CreerRecuRequest,
    ctx: AccessContext = Depends(require_permission(Permission.DONATION_MANAGE)),
    session: Session = Depends(get_session),
):
    """Issue a receipt for one or several dons of the same donor (per-don or annual).

    Validates the association's fiscal identity and the donor's address (both
    mandatory on a receipt), that every entry is an eligible, not-yet-receipted
    don of that donor, then books the receipt with a gapless order number.
    """
    if not body.ecriture_ids:
        raise _bad_request("Sélectionnez au moins un don.")

    association = session.get(Association, ctx.association_id)
    _require_fiscal_identity(association)

    tiers = owned_or_404(
        session, Tiers, body.tiers_id, ctx.association_id, "Donateur introuvable"
    )
    if tiers.type != TypeTiers.DONATEUR:
        raise _bad_request("Le tiers sélectionné n'est pas un donateur.")
    _require_donor_address(tiers)

    eligible = {
        don.ecriture_id: don
        for don in _eligible_dons(
            session,
            ctx.association_id,
            tiers_id=body.tiers_id,
            only_unreceipted=True,
        )
    }
    montant = Decimal("0.00")
    for eid in body.ecriture_ids:
        don = eligible.get(eid)
        if don is None:
            raise _bad_request(
                "Un don est introuvable, déjà reçu, ou n'appartient pas à ce donateur."
            )
        montant += don.montant

    recu = RecuFiscal(
        association_id=ctx.association_id,
        numero=_next_numero(session, ctx.association_id),
        tiers_id=tiers.id,
        date=body.date,
        annee=body.annee,
        montant=montant,
        forme=body.forme,
        mode_reglement=body.mode_reglement,
        created_by=ctx.user.id,
    )
    session.add(recu)
    session.flush()  # parent before children (FK ordering on Postgres)
    for eid in body.ecriture_ids:
        session.add(RecuFiscalLigne(recu_fiscal_id=recu.id, ecriture_id=eid))
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.RECU_CREATE,
        target_type="recu_fiscal",
        target_id=recu.id,
        detail=f"reçu n° {recu.numero} — {tiers.nom}",
    )
    session.commit()
    session.refresh(recu)
    return _to_read(recu, tiers.nom)


@router.get("/recus/{recu_id}/pdf")
def recu_pdf(
    recu_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.DONATION_MANAGE)),
    session: Session = Depends(get_session),
):
    """The receipt as a compliant PDF (streamed as an attachment, nosniff)."""
    recu = owned_or_404(
        session, RecuFiscal, recu_id, ctx.association_id, "Reçu introuvable"
    )
    if recu.annule:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Ce reçu a été annulé."
        )
    association = session.get(Association, ctx.association_id)
    tiers = session.get(Tiers, recu.tiers_id)
    content = documents.recu_pdf(association=association, tiers=tiers, recu=recu)
    filename = f"recu-fiscal-{recu.numero}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{filename}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/recus/{recu_id}", status_code=status.HTTP_204_NO_CONTENT)
def annuler_recu(
    recu_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.DONATION_MANAGE)),
    session: Session = Depends(get_session),
):
    """Cancel a receipt: free its dons but keep the numbered row.

    A receipt is never hard-deleted — its order number must never be reused
    (a donor could hold a printed copy). Cancelling detaches the dons (they can
    be receipted again) and marks the row ``annule``, keeping the audit trail and
    a permanent, gapless numbering.
    """
    recu = owned_or_404(
        session, RecuFiscal, recu_id, ctx.association_id, "Reçu introuvable"
    )
    if recu.annule:
        return
    for ligne in session.exec(
        select(RecuFiscalLigne).where(RecuFiscalLigne.recu_fiscal_id == recu.id)
    ).all():
        session.delete(ligne)
    recu.annule = True
    session.add(recu)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.RECU_DELETE,
        target_type="recu_fiscal",
        target_id=recu_id,
        detail=f"annulation reçu n° {recu.numero}",
    )
    session.commit()
