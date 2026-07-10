"""Entry builders shared by creation, edition and replacement.

Each returns an unsaved ``Ecriture`` (lignes attached, balance-validated) for a
single voucher number; the caller owns auditing and the transaction. Sharing
them keeps creation, brouillon edition and contre-passation replacement in
lockstep — one resolution/validation path per origine, no drift.
"""

from decimal import Decimal

from sqlmodel import Session, SQLModel, select

from accounting_engine import (
    JOURNAL_DIVERS,
    EntryError,
    build_ecriture_simple,
    build_ecriture_virement,
    validate_lignes,
)
from audit import AuditAction
from auth_context import AccessContext
from authz import Permission
from models import (
    Association,
    CategorieSaisie,
    Compte,
    Ecriture,
    EcritureOrigine,
    LigneEcriture,
)

from .resolution import (
    _FINANCIAL_CLASS,
    _bad_request,
    _journal_by_code,
    _open_exercice,
    _owned_compte,
    _owned_journal,
    _owned_treasury,
    _resolve_compte_tva,
    _resolve_evenement_id,
    _resolve_tiers_id,
)
from .schemas import (
    EcritureContenu,
    SaisieManuelleRequest,
    SaisieSimpleRequest,
    VirementRequest,
)

# Origine ↔ the permission that authorizes creating/editing that kind of entry.
_CONTENU_PERMISSION = {
    EcritureOrigine.SAISIE_SIMPLE: Permission.ENTRY_CREATE_SIMPLE,
    EcritureOrigine.VIREMENT: Permission.ENTRY_CREATE_TRANSFER,
    EcritureOrigine.MANUELLE: Permission.ENTRY_CREATE_MANUAL,
}

# Origine ↔ the audit action recorded when an entry of that kind is created.
_CREATE_AUDIT = {
    EcritureOrigine.SAISIE_SIMPLE: AuditAction.ECRITURE_CREATE_SIMPLE,
    EcritureOrigine.VIREMENT: AuditAction.ECRITURE_CREATE_VIREMENT,
    EcritureOrigine.MANUELLE: AuditAction.ECRITURE_CREATE_MANUAL,
}


def _build_simple_entry(
    session: Session, ctx: AccessContext, body: SaisieSimpleRequest, numero_piece: int
) -> Ecriture:
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
    libelle = (body.libelle or "").strip() or categorie.libelle.strip()

    # VAT is honoured only when the régime is on (server-side masking — a
    # client-sent rate is never trusted to enable it). The effective rate is the
    # per-entry override if given, else the category default; a positive rate
    # makes the montant TTC and books the déductible/collectée line.
    tva_taux: Decimal | None = None
    compte_tva_id: str | None = None
    association = session.get(Association, ctx.association_id)
    if association is not None and association.regime_tva:
        taux = body.tva_taux if body.tva_taux is not None else categorie.tva_taux
        if taux is not None and taux > 0:
            tva_taux = taux
            compte_tva_id = _resolve_compte_tva(
                session, ctx.association_id, categorie.sens
            ).id

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
            numero_piece=numero_piece,
            created_by=ctx.user.id,
            tva_taux=tva_taux,
            compte_tva_id=compte_tva_id,
        )
    except EntryError as exc:
        raise _bad_request(str(exc))

    ecriture.categorie_id = categorie.id  # remembered for "by category" views
    ecriture.tiers_id = _resolve_tiers_id(session, ctx.association_id, body.tiers_id)
    ecriture.evenement_id = _resolve_evenement_id(
        session, ctx.association_id, body.evenement_id
    )
    ecriture.reference_externe = body.reference_externe
    ecriture.mode_reglement = body.mode_reglement
    return ecriture


def _build_virement_entry(
    session: Session, ctx: AccessContext, body: VirementRequest, numero_piece: int
) -> Ecriture:
    source = _owned_treasury(session, ctx.association_id, body.compte_source_id)
    destination = _owned_treasury(
        session, ctx.association_id, body.compte_destination_id
    )
    journal = _journal_by_code(session, ctx.association_id, JOURNAL_DIVERS)
    exercice = _open_exercice(session, ctx.association_id, body.date)
    libelle = (body.libelle or "").strip() or (
        f"Virement {source.libelle} → {destination.libelle}"
    )

    try:
        ecriture = build_ecriture_virement(
            association_id=ctx.association_id,
            exercice_id=exercice.id,
            journal_id=journal.id,
            compte_source_id=source.id,
            compte_destination_id=destination.id,
            montant=body.montant,
            date_ecriture=body.date,
            libelle=libelle,
            numero_piece=numero_piece,
            created_by=ctx.user.id,
        )
    except EntryError as exc:
        raise _bad_request(str(exc))

    ecriture.reference_externe = body.reference_externe
    ecriture.mode_reglement = body.mode_reglement
    return ecriture


def _build_manuelle_entry(
    session: Session, ctx: AccessContext, body: SaisieManuelleRequest, numero_piece: int
) -> Ecriture:
    journal = _owned_journal(session, ctx.association_id, body.journal_id)
    exercice = _open_exercice(session, ctx.association_id, body.date)

    # Resolve every referenced account in one query (vs. one round-trip per line),
    # then confirm each requested id is an active account of this association.
    requested_ids = {ligne.compte_id for ligne in body.lignes}
    valid_ids = (
        set(
            session.exec(
                select(Compte.id).where(
                    Compte.id.in_(requested_ids),
                    Compte.association_id == ctx.association_id,
                    Compte.is_active.is_(True),
                )
            ).all()
        )
        if requested_ids
        else set()
    )

    lignes: list[LigneEcriture] = []
    for ligne in body.lignes:
        if ligne.compte_id not in valid_ids:
            raise _bad_request("Compte introuvable ou inactif.")
        lignes.append(
            LigneEcriture(
                compte_id=ligne.compte_id,
                libelle=(ligne.libelle or body.libelle),
                debit=ligne.debit,
                credit=ligne.credit,
            )
        )

    try:
        validate_lignes(lignes)
    except EntryError as exc:
        raise _bad_request(str(exc))

    return Ecriture(
        association_id=ctx.association_id,
        exercice_id=exercice.id,
        journal_id=journal.id,
        date=body.date,
        numero_piece=numero_piece,
        libelle=body.libelle,
        tiers_id=_resolve_tiers_id(session, ctx.association_id, body.tiers_id),
        evenement_id=_resolve_evenement_id(
            session, ctx.association_id, body.evenement_id
        ),
        reference_externe=body.reference_externe,
        mode_reglement=body.mode_reglement,
        origine=EcritureOrigine.MANUELLE,
        created_by=ctx.user.id,
        lignes=lignes,
    )


def _resolve_contenu(contenu: EcritureContenu) -> tuple[EcritureOrigine, SQLModel]:
    """Return the single provided content variant as ``(origine, body)`` (else 400)."""
    variants = [
        (EcritureOrigine.SAISIE_SIMPLE, contenu.simple),
        (EcritureOrigine.VIREMENT, contenu.virement),
        (EcritureOrigine.MANUELLE, contenu.manuelle),
    ]
    provided = [(origine, body) for origine, body in variants if body is not None]
    if len(provided) != 1:
        raise _bad_request(
            "Fournir exactement une variante de contenu (simple, virement ou manuelle)."
        )
    return provided[0]


def _build_entry_from_contenu(
    session: Session,
    ctx: AccessContext,
    origine: EcritureOrigine,
    body: SQLModel,
    numero_piece: int,
) -> Ecriture:
    if origine is EcritureOrigine.SAISIE_SIMPLE:
        return _build_simple_entry(session, ctx, body, numero_piece)
    if origine is EcritureOrigine.VIREMENT:
        return _build_virement_entry(session, ctx, body, numero_piece)
    return _build_manuelle_entry(session, ctx, body, numero_piece)
