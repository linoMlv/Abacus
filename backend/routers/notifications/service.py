"""What awaits a member, kept in step with the association's real state (C28).

The bell is derived, not hand-maintained: on every read we recompute the subjects
that concern *this* reader — filtered by the permissions they actually hold — then
reconcile them with what is stored. A subject that is still pending keeps its row
(so a read one stays read), a new one is inserted, and one that has been settled
is dropped. Operator broadcasts carry no subject and are never touched.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlmodel import Session, select

from auth_context import AccessContext
from authz import Permission
from models import (
    Ecriture,
    EcritureStatut,
    LigneBancaire,
    LigneBancaireStatut,
    Notification,
    NotificationType,
)
from routers.synthese.service import alertes

# Beyond this, the bell would be a wall: the journal is the place to work through
# a backlog of drafts, not a notification list.
MAX_DRAFT_NOTIFICATIONS = 20


@dataclass(frozen=True)
class Subject:
    """One pending thing: its stable key, and how to say it."""

    cle: str
    type: NotificationType
    titre: str
    message: str | None
    lien: str | None


def _drafts_to_validate(session: Session, ctx: AccessContext) -> list[Subject]:
    """Drafts *someone else* left pending — mine are not news to me."""
    drafts = session.exec(
        select(Ecriture)
        .where(
            Ecriture.association_id == ctx.association_id,
            Ecriture.statut == EcritureStatut.BROUILLON,
            Ecriture.created_by != ctx.user.id,
        )
        .order_by(Ecriture.date.desc())
        .limit(MAX_DRAFT_NOTIFICATIONS)
    ).all()
    return [
        Subject(
            cle=f"ecriture:{e.id}",
            type=NotificationType.ECRITURE_A_VALIDER,
            titre="Écriture à valider",
            message=f"Pièce n° {e.numero_piece} — {e.libelle}",
            lien="/journal",
        )
        for e in drafts
    ]


def _unreconciled_accounts(session: Session, association_id: str) -> list[Subject]:
    lignes = session.exec(
        select(LigneBancaire).where(
            LigneBancaire.association_id == association_id,
            LigneBancaire.statut == LigneBancaireStatut.NON_RAPPROCHE,
        )
    ).all()
    par_compte: dict[str, int] = {}
    for ligne in lignes:
        par_compte[ligne.compte_id] = par_compte.get(ligne.compte_id, 0) + 1
    return [
        Subject(
            cle=f"banque:{compte_id}",
            type=NotificationType.BANQUE_A_RAPPROCHER,
            titre="Relevé à rapprocher",
            message=f"{nb} mouvement{'s' if nb > 1 else ''} bancaire"
            f"{'s' if nb > 1 else ''} en attente",
            lien="/banque",
        )
        for compte_id, nb in par_compte.items()
    ]


def subjects_for(session: Session, ctx: AccessContext) -> list[Subject]:
    """The pending subjects this reader may actually act on.

    Permission-filtered by design: telling a viewer to close an exercice they may
    not close is noise, and telling them *what* is pending in a screen they cannot
    reach would leak work they have no part in.
    """
    subjects: list[Subject] = []
    etat = alertes(session, ctx.association_id)

    if Permission.ENTRY_VALIDATE in ctx.permissions:
        subjects += _drafts_to_validate(session, ctx)

    if Permission.EXERCISE_CLOSE in ctx.permissions:
        subjects += [
            Subject(
                cle=f"exercice:{a.exercice_id}",
                type=NotificationType.EXERCICE_A_CLOTURER,
                titre="Exercice à clôturer",
                message=f"{a.libelle} s’est terminé le {a.date_fin:%d/%m/%Y}",
                lien="/parametres?tab=exercices",
            )
            for a in etat.exercices_a_cloturer
        ]

    if Permission.BUDGET_MANAGE in ctx.permissions:
        subjects += [
            Subject(
                cle=f"budget:{a.categorie_id}",
                type=NotificationType.BUDGET_DEPASSE,
                titre="Budget dépassé",
                message=f"{a.libelle} : {a.realise} € dépensés pour "
                f"{a.montant_prevu} € prévus",
                lien="/budget",
            )
            for a in etat.budgets_depasses
        ]

    if Permission.EVENT_MANAGE in ctx.permissions:
        subjects += [
            Subject(
                cle=f"evenement:{a.evenement_id}",
                type=NotificationType.EVENEMENT_DEPASSE,
                titre="Événement au-delà de son budget",
                message=f"{a.nom} : {a.realise_depenses} € dépensés pour "
                f"{a.budget_depenses} € prévus",
                lien="/synthese",
            )
            for a in etat.evenements_depasses
        ]

    if Permission.BANK_RECONCILE in ctx.permissions:
        subjects += _unreconciled_accounts(session, ctx.association_id)

    return subjects


def sync(session: Session, ctx: AccessContext) -> None:
    """Reconcile the caller's derived notifications with the current state."""
    subjects = {s.cle: s for s in subjects_for(session, ctx)}
    existing = session.exec(
        select(Notification).where(
            Notification.association_id == ctx.association_id,
            Notification.user_id == ctx.user.id,
            Notification.cle.is_not(None),
        )
    ).all()

    for notification in existing:
        subject = subjects.pop(notification.cle, None)
        if subject is None:
            # Settled since last time: the bell stops ringing for it.
            session.delete(notification)
        elif notification.message != subject.message:
            # Same subject, moved on (e.g. two more lines to reconcile).
            notification.message = subject.message
            session.add(notification)

    for subject in subjects.values():
        session.add(
            Notification(
                association_id=ctx.association_id,
                user_id=ctx.user.id,
                type=subject.type,
                titre=subject.titre,
                message=subject.message,
                lien=subject.lien,
                cle=subject.cle,
            )
        )
    session.commit()


def list_for(session: Session, ctx: AccessContext) -> list[Notification]:
    """The caller's notifications: unread first, most recent first."""
    return list(
        session.exec(
            select(Notification)
            .where(
                Notification.association_id == ctx.association_id,
                Notification.user_id == ctx.user.id,
            )
            .order_by(Notification.lu_at.is_not(None), Notification.created_at.desc())
        ).all()
    )


def mark_all_read(session: Session, ctx: AccessContext) -> None:
    now = datetime.now(UTC)
    for notification in session.exec(
        select(Notification).where(
            Notification.association_id == ctx.association_id,
            Notification.user_id == ctx.user.id,
            Notification.lu_at.is_(None),
        )
    ).all():
        notification.lu_at = now
        session.add(notification)
    session.commit()
