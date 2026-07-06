"""Budget read assembly and upsert (tenant-scoped, no rendering).

The prévu amounts live in ``Budget``/``LigneBudget``; the réalisé is always
recomputed from the ledger via :mod:`budget_engine`. Reading returns every
active category (a full grid), so the treasurer can fill any cell. Every id from
the client is re-scoped to the active association before use.
"""

from datetime import date
from decimal import Decimal

from fastapi import HTTPException, status
from sqlmodel import Session, desc, select

from accounting_engine import ZERO, find_open_exercice
from audit import AuditAction, record_audit
from auth_context import owned_or_404
from budget_engine import build_budget_view, load_prevu, realise_par_categorie
from models import (
    Budget,
    BudgetRead,
    BudgetUpsert,
    CategorieSaisie,
    Exercice,
    LigneBudget,
    LigneBudgetRead,
)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def resolve_exercice(
    session: Session, association_id: str, exercice_id: str | None
) -> Exercice:
    """The requested exercice (owned) or, by default, the open one, else the latest."""
    if exercice_id:
        return owned_or_404(
            session, Exercice, exercice_id, association_id, "Exercice introuvable"
        )
    exercice = find_open_exercice(session, association_id, date.today())
    if exercice is not None:
        return exercice
    exercice = session.exec(
        select(Exercice)
        .where(Exercice.association_id == association_id)
        .order_by(desc(Exercice.date_debut))
    ).first()
    if exercice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Aucun exercice."
        )
    return exercice


def _active_categories(session: Session, association_id: str) -> list[CategorieSaisie]:
    return session.exec(
        select(CategorieSaisie).where(
            CategorieSaisie.association_id == association_id,
            CategorieSaisie.is_active.is_(True),
        )
    ).all()


def _budget_row(
    session: Session, association_id: str, exercice_id: str
) -> Budget | None:
    return session.exec(
        select(Budget).where(
            Budget.association_id == association_id,
            Budget.exercice_id == exercice_id,
        )
    ).first()


def build_read(session: Session, association_id: str, exercice: Exercice) -> BudgetRead:
    """Assemble the full budget of ``exercice``: every active category + totals."""
    categories = _active_categories(session, association_id)
    prevu = load_prevu(session, association_id, exercice.id)
    realise = realise_par_categorie(session, association_id, exercice.id)
    view = build_budget_view(categories, prevu, realise)
    return BudgetRead(
        exercice_id=exercice.id,
        exercice_libelle=exercice.libelle,
        exercice_statut=exercice.statut,
        lignes=[
            LigneBudgetRead(
                categorie_id=ligne.categorie_id,
                libelle=ligne.libelle,
                sens=ligne.sens,
                montant_prevu=ligne.montant_prevu,
                realise=ligne.realise,
                ecart=ligne.ecart,
            )
            for ligne in view.lignes
        ],
        total_recettes_prevu=view.total_recettes_prevu,
        total_recettes_realise=view.total_recettes_realise,
        total_depenses_prevu=view.total_depenses_prevu,
        total_depenses_realise=view.total_depenses_realise,
        resultat_prevu=view.resultat_prevu,
        resultat_realise=view.resultat_realise,
    )


def upsert(
    session: Session, association_id: str, actor_user_id: str, body: BudgetUpsert
) -> BudgetRead:
    """Replace the exercice budget with the given prévu amounts (a full grid).

    Each category and the exercice are re-scoped to the association; a negative
    amount is refused; a zero amount leaves no line. Idempotent — re-sending the
    same body yields the same budget.
    """
    exercice = owned_or_404(
        session, Exercice, body.exercice_id, association_id, "Exercice introuvable"
    )

    montants: dict[str, Decimal] = {}
    for item in body.lignes:
        if item.montant_prevu < ZERO:
            raise _bad_request("Les montants prévus ne peuvent pas être négatifs.")
        categorie = owned_or_404(
            session,
            CategorieSaisie,
            item.categorie_id,
            association_id,
            "Catégorie introuvable",
        )
        if not categorie.is_active:
            raise _bad_request("Impossible de budgéter une catégorie archivée.")
        montants[item.categorie_id] = item.montant_prevu  # last wins on duplicates

    budget = _budget_row(session, association_id, exercice.id)
    if budget is None:
        budget = Budget(association_id=association_id, exercice_id=exercice.id)
        session.add(budget)
        session.flush()  # need its id before inserting the lines (FK ordering)
    else:
        for old in session.exec(
            select(LigneBudget).where(LigneBudget.budget_id == budget.id)
        ).all():
            session.delete(old)
        session.flush()
    nb_lignes = 0
    for categorie_id, montant in montants.items():
        if montant > ZERO:
            session.add(
                LigneBudget(
                    budget_id=budget.id,
                    categorie_id=categorie_id,
                    montant_prevu=montant,
                )
            )
            nb_lignes += 1

    record_audit(
        session,
        association_id=association_id,
        actor_user_id=actor_user_id,
        action=AuditAction.BUDGET_UPDATE,
        target_type="budget",
        target_id=budget.id,
        detail=f"exercice={exercice.libelle} lignes={nb_lignes}",
    )
    session.commit()
    return build_read(session, association_id, exercice)
