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
    ECRITURE_CREATE_VIREMENT = "ecriture.create_virement"
    ECRITURE_CREATE_MANUAL = "ecriture.create_manual"
    ECRITURE_UPDATE = "ecriture.update"
    ECRITURE_VALIDATE = "ecriture.validate"
    ECRITURE_DELETE = "ecriture.delete"
    ECRITURE_CONTREPASSATION = "ecriture.contrepassation"
    COMPTE_TRESORERIE_CREATE = "compte_tresorerie.create"
    COMPTE_TRESORERIE_UPDATE = "compte_tresorerie.update"
    CATEGORIE_CREATE = "categorie.create"
    CATEGORIE_UPDATE = "categorie.update"
    TIERS_CREATE = "tiers.create"
    TIERS_UPDATE = "tiers.update"
    RECU_CREATE = "recu.create"
    RECU_DELETE = "recu.delete"
    JUSTIFICATIF_UPLOAD = "justificatif.upload"
    JUSTIFICATIF_DELETE = "justificatif.delete"
    EVENEMENT_CREATE = "evenement.create"
    EVENEMENT_UPDATE = "evenement.update"
    EXERCICE_CREATE = "exercice.create"
    EXERCICE_CLOTURE = "exercice.cloture"
    ANNEXE_UPDATE = "annexe.update"
    BUDGET_UPDATE = "budget.update"
    RELEVE_IMPORT = "releve.import"
    RELEVE_DELETE = "releve.delete"
    LIGNE_BANCAIRE_RAPPROCHE = "ligne_bancaire.rapproche"
    LIGNE_BANCAIRE_DELETTRAGE = "ligne_bancaire.delettrage"
    RECURRENCE_CREATE = "recurrence.create"
    RECURRENCE_UPDATE = "recurrence.update"
    RECURRENCE_DELETE = "recurrence.delete"
    RECURRENCE_GENERATE = "recurrence.generate"
    APIKEY_CREATE = "apikey.create"
    APIKEY_REVOKE = "apikey.revoke"
    MCP_TOOL_CALL = "mcp.tool_call"


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
