"""Tenant-scoped resolution helpers.

Every reference coming from the client (category, account, journal, entry id) is
re-resolved against the active association here before use — an id is never
trusted to authorize access.
"""

from datetime import date

from fastapi import HTTPException, status
from sqlmodel import Session, select

from accounting_engine import find_open_exercice
from audit import AuditAction, record_audit
from auth_context import AccessContext, owned_or_404
from authz import Permission
from models import Compte, Ecriture, Evenement, Exercice, Journal, SensCategorie, Tiers

_FINANCIAL_CLASS = 5  # comptes de trésorerie (512 banque, 531 caisse, …)

# VAT counterpart account per sens: recette collects (44571), dépense deducts (44566).
_TVA_ACCOUNT = {
    SensCategorie.RECETTE: "44571",  # TVA collectée
    SensCategorie.DEPENSE: "44566",  # TVA déductible
}


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _require(ctx: AccessContext, permission: Permission) -> None:
    """Server-side permission check on the effective set (zero trust on the client)."""
    if permission not in ctx.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
        )


def _open_exercice(session: Session, association_id: str, jour: date) -> Exercice:
    exercice = find_open_exercice(session, association_id, jour)
    if exercice is None:
        raise _bad_request("Aucun exercice ouvert ne couvre cette date.")
    return exercice


def _owned_compte(session: Session, association_id: str, compte_id: str) -> Compte:
    compte = session.exec(
        select(Compte).where(
            Compte.id == compte_id,
            Compte.association_id == association_id,
            Compte.is_active.is_(True),
        )
    ).first()
    if compte is None:
        raise _bad_request("Compte introuvable ou inactif.")
    return compte


def _owned_journal(session: Session, association_id: str, journal_id: str) -> Journal:
    journal = session.exec(
        select(Journal).where(
            Journal.id == journal_id, Journal.association_id == association_id
        )
    ).first()
    if journal is None:
        raise _bad_request("Journal introuvable.")
    return journal


def _owned_treasury(session: Session, association_id: str, compte_id: str) -> Compte:
    """Resolve an active *treasury* account of the association (else 400)."""
    compte = _owned_compte(session, association_id, compte_id)
    if compte.type_tresorerie is None:
        raise _bad_request("Le compte sélectionné n'est pas un compte de trésorerie.")
    return compte


def _resolve_tiers_id(
    session: Session, association_id: str, tiers_id: str | None
) -> str | None:
    """Validate an optional tiers reference belongs to the association (else 400)."""
    if tiers_id is None:
        return None
    tiers = session.exec(
        select(Tiers).where(
            Tiers.id == tiers_id,
            Tiers.association_id == association_id,
            Tiers.is_active.is_(True),
        )
    ).first()
    if tiers is None:
        raise _bad_request("Tiers introuvable ou inactif.")
    return tiers.id


def _resolve_evenement_id(
    session: Session, association_id: str, evenement_id: str | None
) -> str | None:
    """Validate an optional event reference belongs to the association (else 400)."""
    if evenement_id is None:
        return None
    evenement = session.exec(
        select(Evenement).where(
            Evenement.id == evenement_id,
            Evenement.association_id == association_id,
        )
    ).first()
    if evenement is None:
        raise _bad_request("Événement introuvable.")
    return evenement.id


def _resolve_compte_tva(
    session: Session, association_id: str, sens: SensCategorie
) -> Compte:
    """Resolve the VAT account (44571 collectée / 44566 déductible) of the sens."""
    numero = _TVA_ACCOUNT[sens]
    compte = session.exec(
        select(Compte).where(
            Compte.association_id == association_id,
            Compte.numero == numero,
            Compte.is_active.is_(True),
        )
    ).first()
    if compte is None:
        raise _bad_request(f"Compte de TVA {numero} introuvable.")
    return compte


def _journal_by_code(session: Session, association_id: str, code: str) -> Journal:
    journal = session.exec(
        select(Journal).where(
            Journal.association_id == association_id, Journal.code == code
        )
    ).first()
    if journal is None:
        raise _bad_request(f"Journal {code} introuvable.")
    return journal


def _owned_ecriture(
    session: Session, association_id: str, ecriture_id: str
) -> Ecriture:
    return owned_or_404(
        session, Ecriture, ecriture_id, association_id, "Écriture introuvable"
    )


def _owned_ecritures(
    session: Session, association_id: str, ids: list[str]
) -> dict[str, Ecriture]:
    """Resolve the requested ids that belong to the association, keyed by id.

    A single tenant-scoped query; ids of another tenant (or unknown) are simply
    absent from the result, so the caller reports them as ignored (no leak).
    """
    if not ids:
        return {}
    rows = session.exec(
        select(Ecriture).where(
            Ecriture.id.in_(ids), Ecriture.association_id == association_id
        )
    ).all()
    return {e.id: e for e in rows}


def _audit_ecriture(
    session: Session,
    ctx: AccessContext,
    action: AuditAction,
    ecriture: Ecriture,
) -> None:
    """Record an audit entry for an action on ``ecriture`` (no commit)."""
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=action,
        target_type="ecriture",
        target_id=ecriture.id,
        detail=f"pièce {ecriture.numero_piece}",
    )
