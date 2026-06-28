"""Custom entry categories (catégories de saisie).

A category is the plain-language wording a volunteer picks ("Buvette", "Loyer");
it bridges to a produit/charge account and a default journal (§15.5). Soft
creation needs only a libellé + sens — the account is auto-assigned (recette →
758 Produits divers, dépense → 658 Charges diverses) and the expert can reassign
it. Deactivating never deletes (entries store the *account*, not the category).
Every reference from the client is re-scoped to the active association.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, SQLModel, asc, select

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
    CategorieSaisie,
    CategorieSaisieRead,
    Compte,
    CompteType,
    Journal,
    SensCategorie,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["categories"])

# Soft-creation defaults per sens: (compte numéro, journal code, attendu type).
_DEFAULTS: dict[SensCategorie, tuple[str, str, CompteType]] = {
    SensCategorie.RECETTE: ("758", "VE", CompteType.PRODUIT),
    SensCategorie.DEPENSE: ("658", "AC", CompteType.CHARGE),
}


class CreateCategorieRequest(SQLModel):
    sens: SensCategorie
    libelle: str
    compte_id: str | None = None  # expert override; else auto (758/658)


class UpdateCategorieRequest(SQLModel):
    libelle: str | None = None
    compte_id: str | None = None
    ordre: int | None = None
    is_active: bool | None = None


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _compte_by_numero(session: Session, association_id: str, numero: str) -> Compte:
    compte = session.exec(
        select(Compte).where(
            Compte.association_id == association_id, Compte.numero == numero
        )
    ).first()
    if compte is None:
        raise _bad_request(f"Référentiel comptable incomplet (compte {numero}).")
    return compte


def _resolved_compte_id(
    session: Session, ctx: AccessContext, sens: SensCategorie, compte_id: str | None
) -> str:
    """The account a category points at: an expert override (type-checked) or the
    soft default for the sens."""
    numero, _, attendu = _DEFAULTS[sens]
    if compte_id is None:
        return _compte_by_numero(session, ctx.association_id, numero).id
    compte = owned_or_404(
        session, Compte, compte_id, ctx.association_id, "Compte introuvable"
    )
    if compte.type != attendu:
        raise _bad_request(
            f"Une catégorie de {sens.value} doit pointer vers un compte de "
            f"{attendu.value}."
        )
    return compte.id


def _libelle_taken(
    session: Session, association_id: str, libelle: str, exclude_id: str | None = None
) -> bool:
    statement = select(CategorieSaisie).where(
        CategorieSaisie.association_id == association_id,
        CategorieSaisie.libelle == libelle,
    )
    existing = session.exec(statement).first()
    return existing is not None and existing.id != exclude_id


@router.get("/categories", response_model=list[CategorieSaisieRead])
def list_categories(
    sens: SensCategorie | None = None,
    include_inactive: bool = False,
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    statement = select(CategorieSaisie).where(
        CategorieSaisie.association_id == ctx.association_id
    )
    if sens is not None:
        statement = statement.where(CategorieSaisie.sens == sens)
    if not include_inactive:
        statement = statement.where(CategorieSaisie.is_active.is_(True))
    statement = statement.order_by(asc(CategorieSaisie.ordre))
    return session.exec(statement).all()


@router.post(
    "/categories",
    response_model=CategorieSaisieRead,
    status_code=status.HTTP_201_CREATED,
)
def create_categorie(
    body: CreateCategorieRequest,
    ctx: AccessContext = Depends(require_permission(Permission.CATEGORIE_MANAGE)),
    session: Session = Depends(get_session),
):
    libelle = body.libelle.strip()
    if not libelle:
        raise _bad_request("Le libellé de la catégorie est requis.")
    if _libelle_taken(session, ctx.association_id, libelle):
        raise _bad_request("Une catégorie porte déjà ce nom.")

    compte_id = _resolved_compte_id(session, ctx, body.sens, body.compte_id)
    journal_code = _DEFAULTS[body.sens][1]
    journal = session.exec(
        select(Journal).where(
            Journal.association_id == ctx.association_id, Journal.code == journal_code
        )
    ).first()
    if journal is None:
        raise _bad_request(f"Référentiel comptable incomplet (journal {journal_code}).")

    max_ordre = session.exec(
        select(CategorieSaisie.ordre)
        .where(CategorieSaisie.association_id == ctx.association_id)
        .order_by(CategorieSaisie.ordre.desc())
    ).first()
    categorie = CategorieSaisie(
        association_id=ctx.association_id,
        sens=body.sens,
        libelle=libelle,
        compte_id=compte_id,
        journal_id=journal.id,
        ordre=(max_ordre + 1) if max_ordre is not None else 0,
    )
    session.add(categorie)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.CATEGORIE_CREATE,
        target_type="categorie_saisie",
        target_id=categorie.id,
        detail=f"{body.sens.value} {libelle}",
    )
    session.commit()
    session.refresh(categorie)
    return categorie


@router.patch("/categories/{categorie_id}", response_model=CategorieSaisieRead)
def update_categorie(
    categorie_id: str,
    body: UpdateCategorieRequest,
    ctx: AccessContext = Depends(require_permission(Permission.CATEGORIE_MANAGE)),
    session: Session = Depends(get_session),
):
    """Rename / reassign account / reorder / deactivate. The sens is immutable
    (it drives the account nature); deactivating never deletes."""
    categorie = owned_or_404(
        session,
        CategorieSaisie,
        categorie_id,
        ctx.association_id,
        "Catégorie introuvable",
    )

    if body.libelle is not None:
        libelle = body.libelle.strip()
        if not libelle:
            raise _bad_request("Le libellé ne peut pas être vide.")
        if _libelle_taken(
            session, ctx.association_id, libelle, exclude_id=categorie.id
        ):
            raise _bad_request("Une catégorie porte déjà ce nom.")
        categorie.libelle = libelle
    if body.compte_id is not None:
        categorie.compte_id = _resolved_compte_id(
            session, ctx, categorie.sens, body.compte_id
        )
    if body.ordre is not None:
        categorie.ordre = body.ordre
    if body.is_active is not None:
        categorie.is_active = body.is_active

    session.add(categorie)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.CATEGORIE_UPDATE,
        target_type="categorie_saisie",
        target_id=categorie.id,
        detail=categorie.libelle,
    )
    session.commit()
    session.refresh(categorie)
    return categorie
