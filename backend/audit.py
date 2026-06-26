"""Business audit trail: record who performed a sensitive action and when.

Separate from the HTTP request log (``LogEntry``): this captures domain actions
required by the accounting-integrity rules (plan §10). ``record_audit`` only
stages the row — the caller commits it inside the same transaction as the action
itself, so the trail is atomic with what it describes (no orphan or missing
entry).
"""

from sqlmodel import Session

from models import AuditLog


class AuditAction:
    """Stable action identifiers (``domain.action``). Persisted — do not rename."""

    ECRITURE_CREATE_SIMPLE = "ecriture.create_simple"
    ECRITURE_CREATE_MANUAL = "ecriture.create_manual"
    ECRITURE_VALIDATE = "ecriture.validate"
    ECRITURE_DELETE = "ecriture.delete"


def record_audit(
    session: Session,
    *,
    association_id: str | None,
    actor_user_id: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: str | None = None,
) -> None:
    """Stage an audit entry (no commit; committed with the action's transaction)."""
    session.add(
        AuditLog(
            association_id=association_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
        )
    )
