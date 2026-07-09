"""Tenant-scoped resolution & seeding for the narrative annexe.

Rubrics belong to an exercice; every id from the client (exercice, rubric) is
re-resolved against the active association via ``owned_or_404`` before use, so a
member of A can never read or edit B's annexe. The default ANC rubric set is
seeded lazily the first time an exercice's annexe is read, which covers both the
exercice seeded at association creation and any opened later — no data migration.
"""

from sqlmodel import Session, asc, select

from auth_context import owned_or_404
from models import (
    DEFAULT_ANNEXE_RUBRIQUES,
    AnnexeRubrique,
    Exercice,
)


def owned_exercice(session: Session, association_id: str, exercice_id: str) -> Exercice:
    return owned_or_404(
        session, Exercice, exercice_id, association_id, "Exercice introuvable"
    )


def owned_rubrique(
    session: Session, association_id: str, rubrique_id: str
) -> AnnexeRubrique:
    return owned_or_404(
        session, AnnexeRubrique, rubrique_id, association_id, "Rubrique introuvable"
    )


def list_rubriques(
    session: Session, association_id: str, exercice_id: str
) -> list[AnnexeRubrique]:
    """Rubrics of an exercice, ordered; seeds the default ANC set if empty."""
    rubriques = _fetch(session, association_id, exercice_id)
    if not rubriques:
        rubriques = _seed_defaults(session, association_id, exercice_id)
    return rubriques


def _fetch(
    session: Session, association_id: str, exercice_id: str
) -> list[AnnexeRubrique]:
    return list(
        session.exec(
            select(AnnexeRubrique)
            .where(
                AnnexeRubrique.association_id == association_id,
                AnnexeRubrique.exercice_id == exercice_id,
            )
            .order_by(asc(AnnexeRubrique.ordre), asc(AnnexeRubrique.titre))
        ).all()
    )


def _seed_defaults(
    session: Session, association_id: str, exercice_id: str
) -> list[AnnexeRubrique]:
    for ordre, titre in enumerate(DEFAULT_ANNEXE_RUBRIQUES):
        session.add(
            AnnexeRubrique(
                association_id=association_id,
                exercice_id=exercice_id,
                titre=titre,
                contenu="",
                ordre=ordre,
            )
        )
    session.commit()
    return _fetch(session, association_id, exercice_id)


def next_ordre(session: Session, association_id: str, exercice_id: str) -> int:
    """One past the highest existing order for the exercice (append at the end)."""
    existing = _fetch(session, association_id, exercice_id)
    return max((r.ordre for r in existing), default=-1) + 1
