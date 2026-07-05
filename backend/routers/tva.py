"""VAT position (état de TVA) for a period.

Nets the collectée (44571) against the déductible (44566) to the amount to remit
(à décaisser, 44551). Validated entries only — a draft never inflates the
official VAT position (D38). Gated by ``REPORT_VIEW``.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlmodel import Session, SQLModel, func, select

from accounting_engine import CENTS, ZERO, exclude_cloture, validated_only
from auth_context import AccessContext, require_permission
from authz import Permission
from database import get_session
from models import Compte, Ecriture, LigneEcriture

from .synthese import service as synthese_service

router = APIRouter(prefix="/api/asso/{association_id}", tags=["tva"])

_COLLECTEE = "44571"
_DEDUCTIBLE = "44566"


class EtatTvaRead(SQLModel):
    date_from: date
    date_to: date
    collectee: Decimal
    deductible: Decimal
    a_decaisser: Decimal  # collectée − déductible (négatif = crédit de TVA)


def _net_on_account(
    session: Session,
    association_id: str,
    numero: str,
    date_from: date,
    date_to: date,
) -> tuple[Decimal, Decimal]:
    """Return (total_debit, total_credit) on an account over the period (validated)."""
    row = session.exec(
        select(
            func.coalesce(func.sum(LigneEcriture.debit), 0),
            func.coalesce(func.sum(LigneEcriture.credit), 0),
        )
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Compte.association_id == association_id,
            Compte.numero == numero,
            Ecriture.date >= date_from,
            Ecriture.date <= date_to,
            validated_only(),
            exclude_cloture(),
        )
    ).first()
    debit, credit = (
        (Decimal(str(row[0])), Decimal(str(row[1]))) if row else (ZERO, ZERO)
    )
    return debit, credit


@router.get("/tva", response_model=EtatTvaRead)
def etat_tva(
    date_from: date | None = None,
    date_to: date | None = None,
    ctx: AccessContext = Depends(require_permission(Permission.REPORT_VIEW)),
    session: Session = Depends(get_session),
):
    default_from, default_to = synthese_service.default_range(
        session, ctx.association_id
    )
    date_from = date_from or default_from
    date_to = date_to or default_to
    aid = ctx.association_id

    col_debit, col_credit = _net_on_account(
        session, aid, _COLLECTEE, date_from, date_to
    )
    ded_debit, ded_credit = _net_on_account(
        session, aid, _DEDUCTIBLE, date_from, date_to
    )
    collectee = (col_credit - col_debit).quantize(CENTS)
    deductible = (ded_debit - ded_credit).quantize(CENTS)
    return EtatTvaRead(
        date_from=date_from,
        date_to=date_to,
        collectee=collectee,
        deductible=deductible,
        a_decaisser=(collectee - deductible).quantize(CENTS),
    )
