"""Accounting entries: assisted (simple) and manual creation, read, validation.

Every reference coming from the client (category, account, journal, entry id) is
re-resolved against the active association before use — an id is never trusted
to authorize access. Validated entries are immutable and entries can only be
booked into an *open* fiscal year covering their date.
"""

from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, SQLModel, desc, select

from accounting_engine import (
    EntryError,
    build_ecriture_simple,
    next_numero_piece,
    validate_lignes,
)
from auth_context import AccessContext, get_active_membership, require_permission
from authz import Permission
from database import get_session
from models import (
    CategorieSaisie,
    Compte,
    Ecriture,
    EcritureDetailRead,
    EcritureOrigine,
    EcritureRead,
    EcritureStatut,
    Exercice,
    ExerciceStatut,
    Journal,
    LigneEcriture,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["ecritures"])

_FINANCIAL_CLASS = 5  # comptes de trésorerie (512 banque, 531 caisse, …)


# --- Request schemas ------------------------------------------------------


class SaisieSimpleRequest(SQLModel):
    categorie_id: str
    compte_tresorerie_id: str
    montant: Decimal
    date: date
    libelle: str | None = None


class LigneInput(SQLModel):
    compte_id: str
    libelle: str | None = None
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")


class SaisieManuelleRequest(SQLModel):
    journal_id: str
    date: date
    libelle: str
    lignes: list[LigneInput]


# --- Tenant-scoped resolution helpers -------------------------------------


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _open_exercice(session: Session, association_id: str, jour: date) -> Exercice:
    exercice = session.exec(
        select(Exercice).where(
            Exercice.association_id == association_id,
            Exercice.date_debut <= jour,
            Exercice.date_fin >= jour,
            Exercice.statut == ExerciceStatut.OUVERT,
        )
    ).first()
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


def _owned_ecriture(
    session: Session, association_id: str, ecriture_id: str
) -> Ecriture:
    ecriture = session.exec(
        select(Ecriture).where(
            Ecriture.id == ecriture_id,
            Ecriture.association_id == association_id,
        )
    ).first()
    if ecriture is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Écriture introuvable"
        )
    return ecriture


# --- Creation -------------------------------------------------------------


@router.post(
    "/ecritures/simple",
    response_model=EcritureDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def creer_saisie_simple(
    body: SaisieSimpleRequest,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_CREATE_SIMPLE)),
    session: Session = Depends(get_session),
):
    categorie = session.exec(
        select(CategorieSaisie).where(
            CategorieSaisie.id == body.categorie_id,
            CategorieSaisie.association_id == ctx.association_id,
            CategorieSaisie.is_active.is_(True),
        )
    ).first()
    if categorie is None:
        raise _bad_request("Catégorie introuvable ou inactive.")

    compte_tresorerie = _owned_compte(
        session, ctx.association_id, body.compte_tresorerie_id
    )
    if compte_tresorerie.classe != _FINANCIAL_CLASS:
        raise _bad_request(
            "Le compte de contrepartie doit être un compte de trésorerie (classe 5)."
        )

    exercice = _open_exercice(session, ctx.association_id, body.date)
    libelle = (body.libelle or categorie.libelle).strip() or categorie.libelle

    try:
        ecriture = build_ecriture_simple(
            association_id=ctx.association_id,
            exercice_id=exercice.id,
            journal_id=categorie.journal_id,
            compte_tresorerie_id=compte_tresorerie.id,
            compte_categorie_id=categorie.compte_id,
            sens=categorie.sens,
            montant=body.montant,
            date_ecriture=body.date,
            libelle=libelle,
            numero_piece=next_numero_piece(session, ctx.association_id),
            created_by=ctx.user.id,
        )
    except EntryError as exc:
        raise _bad_request(str(exc))

    session.add(ecriture)
    session.commit()
    session.refresh(ecriture)
    return ecriture


@router.post(
    "/ecritures",
    response_model=EcritureDetailRead,
    status_code=status.HTTP_201_CREATED,
)
def creer_saisie_manuelle(
    body: SaisieManuelleRequest,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_CREATE_MANUAL)),
    session: Session = Depends(get_session),
):
    journal = _owned_journal(session, ctx.association_id, body.journal_id)
    exercice = _open_exercice(session, ctx.association_id, body.date)

    lignes: list[LigneEcriture] = []
    for ligne in body.lignes:
        compte = _owned_compte(session, ctx.association_id, ligne.compte_id)
        lignes.append(
            LigneEcriture(
                compte_id=compte.id,
                libelle=(ligne.libelle or body.libelle),
                debit=ligne.debit,
                credit=ligne.credit,
            )
        )

    try:
        validate_lignes(lignes)
    except EntryError as exc:
        raise _bad_request(str(exc))

    ecriture = Ecriture(
        association_id=ctx.association_id,
        exercice_id=exercice.id,
        journal_id=journal.id,
        date=body.date,
        numero_piece=next_numero_piece(session, ctx.association_id),
        libelle=body.libelle,
        origine=EcritureOrigine.MANUELLE,
        created_by=ctx.user.id,
        lignes=lignes,
    )
    session.add(ecriture)
    session.commit()
    session.refresh(ecriture)
    return ecriture


# --- Read & lifecycle -----------------------------------------------------


@router.get("/ecritures", response_model=list[EcritureRead])
def list_ecritures(
    exercice_id: str | None = None,
    journal_id: str | None = None,
    statut: EcritureStatut | None = None,
    q: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    """The journal: entries of the active association, newest first.

    The optional ``exercice_id`` / ``journal_id`` are plain filters applied on
    top of the mandatory ``association_id`` scope — an id from another tenant
    simply matches nothing, it never widens access.
    """
    statement = select(Ecriture).where(Ecriture.association_id == ctx.association_id)
    if exercice_id is not None:
        statement = statement.where(Ecriture.exercice_id == exercice_id)
    if journal_id is not None:
        statement = statement.where(Ecriture.journal_id == journal_id)
    if statut is not None:
        statement = statement.where(Ecriture.statut == statut)
    if q:
        statement = statement.where(Ecriture.libelle.ilike(f"%{q}%"))
    statement = (
        statement.order_by(desc(Ecriture.date), desc(Ecriture.numero_piece))
        .limit(limit)
        .offset(offset)
    )
    return session.exec(statement).all()


@router.get("/ecritures/{ecriture_id}", response_model=EcritureDetailRead)
def get_ecriture(
    ecriture_id: str,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    return _owned_ecriture(session, ctx.association_id, ecriture_id)


@router.post("/ecritures/{ecriture_id}/validation", response_model=EcritureDetailRead)
def valider_ecriture(
    ecriture_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_VALIDATE)),
    session: Session = Depends(get_session),
):
    ecriture = _owned_ecriture(session, ctx.association_id, ecriture_id)
    if ecriture.statut == EcritureStatut.VALIDEE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Écriture déjà validée."
        )

    ecriture.statut = EcritureStatut.VALIDEE
    ecriture.validated_by = ctx.user.id
    ecriture.validated_at = datetime.now(UTC)
    session.add(ecriture)
    session.commit()
    session.refresh(ecriture)
    return ecriture


@router.delete("/ecritures/{ecriture_id}", status_code=status.HTTP_204_NO_CONTENT)
def supprimer_ecriture(
    ecriture_id: str,
    ctx: AccessContext = Depends(require_permission(Permission.ENTRY_DELETE)),
    session: Session = Depends(get_session),
):
    ecriture = _owned_ecriture(session, ctx.association_id, ecriture_id)
    if ecriture.statut == EcritureStatut.VALIDEE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Une écriture validée ne peut être supprimée "
                "(contre-passation requise)."
            ),
        )
    session.delete(ecriture)
    session.commit()
