from sqlalchemy import func
from sqlmodel import Session, select

from models import Association, Ecriture


def next_numero_piece(session: Session, association_id: str) -> int:
    """Return the next sequential voucher number for ``association_id``.

    Numbering is per association and continuous (``max + 1``). To avoid two
    concurrent writers picking the same number, the association row is locked
    ``FOR UPDATE`` first: the lock is held until the caller's transaction
    commits the new entry, serializing numbering per association. (The lock is a
    no-op on SQLite, which runs one writer at a time anyway; on PostgreSQL it is
    the real guard, backing up the ``(association_id, numero_piece)`` unique
    constraint.)
    """
    session.exec(
        select(Association.id).where(Association.id == association_id).with_for_update()
    ).first()
    current_max = session.exec(
        select(func.max(Ecriture.numero_piece)).where(
            Ecriture.association_id == association_id
        )
    ).one()
    return (current_max or 0) + 1
