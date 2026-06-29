"""Shared journal filtering: the WHERE clauses behind the journal listing.

Extracted so the journal listing (``GET /ecritures``) and the journal export
build the *same* faceted filter from the same definition — one place to scope,
one place to reason about. Every clause is applied on top of a mandatory
``association_id`` scope by the caller; an id from another tenant simply matches
nothing (never widening access).
"""

from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy import or_
from sqlmodel import select

from models import (
    CategorieSaisie,
    Ecriture,
    EcritureOrigine,
    EcritureStatut,
    LigneEcriture,
    SensCategorie,
)


class TypeOperationFilter(str, Enum):
    """Type-first journal filter (§15.3), the vocabulary a treasurer reasons with.

    ``recette`` / ``depense`` are derived from the entry's category sens; a
    ``virement`` from its origine. A manual entry carries no category, so it
    matches none of these three (it only shows when no type filter is set).
    """

    RECETTE = "recette"
    DEPENSE = "depense"
    VIREMENT = "virement"


@dataclass
class JournalFilter:
    """The faceted journal filters (each facet OR-combines its values; AND across)."""

    journal_id: list[str] | None = None
    compte_id: list[str] | None = None
    type_operation: list[TypeOperationFilter] | None = None
    categorie_id: list[str] | None = None
    tiers_id: list[str] | None = None
    evenement_id: list[str] | None = None
    date_from: date | None = None
    date_to: date | None = None
    statut: list[EcritureStatut] | None = None
    q: str | None = None


def _type_operation_clause(association_id: str, types: list[TypeOperationFilter]):
    """OR clause matching entries of any of the requested operation types.

    Virement is identified by its origine; recette/dépense by the sens of the
    entry's category (re-scoped to the association). A manual entry has no
    category, so it matches neither recette nor dépense.
    """
    conditions = []
    sens_wanted = [
        SensCategorie.RECETTE
        if t is TypeOperationFilter.RECETTE
        else SensCategorie.DEPENSE
        for t in types
        if t is not TypeOperationFilter.VIREMENT
    ]
    if sens_wanted:
        conditions.append(
            Ecriture.categorie_id.in_(
                select(CategorieSaisie.id).where(
                    CategorieSaisie.association_id == association_id,
                    CategorieSaisie.sens.in_(sens_wanted),
                )
            )
        )
    if TypeOperationFilter.VIREMENT in types:
        conditions.append(Ecriture.origine == EcritureOrigine.VIREMENT)
    return or_(*conditions)


def journal_filter_clauses(association_id: str, filtre: JournalFilter) -> list:
    """Build the list of SQLAlchemy clauses for ``filtre`` (caller adds the scope).

    Each populated facet contributes one clause (OR within, AND across). Empty
    facets contribute nothing. Use as ``statement.where(*clauses)`` on a statement
    already scoped to ``association_id``.
    """
    clauses = []
    if filtre.journal_id:
        clauses.append(Ecriture.journal_id.in_(filtre.journal_id))
    if filtre.compte_id:
        # Entries with at least one line on one of these accounts (e.g. treasury).
        clauses.append(
            Ecriture.id.in_(
                select(LigneEcriture.ecriture_id).where(
                    LigneEcriture.compte_id.in_(filtre.compte_id)
                )
            )
        )
    if filtre.type_operation:
        clauses.append(_type_operation_clause(association_id, filtre.type_operation))
    if filtre.categorie_id:
        clauses.append(Ecriture.categorie_id.in_(filtre.categorie_id))
    if filtre.tiers_id:
        clauses.append(Ecriture.tiers_id.in_(filtre.tiers_id))
    if filtre.evenement_id:
        clauses.append(Ecriture.evenement_id.in_(filtre.evenement_id))
    if filtre.date_from is not None:
        clauses.append(Ecriture.date >= filtre.date_from)
    if filtre.date_to is not None:
        clauses.append(Ecriture.date <= filtre.date_to)
    if filtre.statut:
        clauses.append(Ecriture.statut.in_(filtre.statut))
    if filtre.q:
        clauses.append(Ecriture.libelle.ilike(f"%{filtre.q}%"))
    return clauses
