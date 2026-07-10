"""Fiscal-year endpoints: list, open, close."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, desc, select

from accounting_engine import (
    CENTS,
    CLASSES_BILAN,
    CLASSES_GESTION,
    ZERO,
    build_ecriture_determination_resultat,
    build_ecriture_report_a_nouveau,
    next_numero_piece,
    resultat_de_gestion,
)
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
    AffectationResultat,
    ClotureResult,
    Ecriture,
    EcritureStatut,
    Exercice,
    ExerciceCreate,
    ExerciceRead,
    ExerciceStatut,
    Journal,
)

from .service import (
    _COMPTE_DEFICIT,
    _COMPTE_EXCEDENT,
    _JOURNAL_CLOTURE,
    _REPORT_DEFICIT,
    _REPORT_EXCEDENT,
    _RESERVES,
    _account_soldes,
    _bad_request,
    _resolve_compte,
    _resolve_next_exercice,
    _validate_now,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["exercices"])


@router.get("/exercices", response_model=list[ExerciceRead])
def list_exercices(
    ctx: AccessContext = Depends(get_active_membership),
    session: Session = Depends(get_session),
):
    statement = (
        select(Exercice)
        .where(Exercice.association_id == ctx.association_id)
        .order_by(desc(Exercice.date_debut))
    )
    return session.exec(statement).all()


@router.post(
    "/exercices", response_model=ExerciceRead, status_code=status.HTTP_201_CREATED
)
def creer_exercice(
    body: ExerciceCreate,
    ctx: AccessContext = Depends(require_permission(Permission.EXERCISE_CLOSE)),
    session: Session = Depends(get_session),
):
    """Open a new fiscal year with parametric dates (shifted years supported).

    Guards: the label must be non-empty, the end must be strictly after the
    start, and the period must not overlap any existing exercice of the
    association (fiscal years partition time, so an entry maps to exactly one).
    """
    libelle = body.libelle.strip()
    if not libelle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le libellé de l'exercice est obligatoire.",
        )
    if body.date_fin <= body.date_debut:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La date de fin doit être postérieure à la date de début.",
        )

    # Overlap: two ranges intersect iff each starts on or before the other ends.
    overlap = session.exec(
        select(Exercice.id).where(
            Exercice.association_id == ctx.association_id,
            Exercice.date_debut <= body.date_fin,
            Exercice.date_fin >= body.date_debut,
        )
    ).first()
    if overlap is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La période chevauche un exercice existant.",
        )

    exercice = Exercice(
        association_id=ctx.association_id,
        libelle=libelle,
        date_debut=body.date_debut,
        date_fin=body.date_fin,
    )
    session.add(exercice)
    record_audit(
        session,
        association_id=ctx.association_id,
        actor_user_id=ctx.user.id,
        action=AuditAction.EXERCICE_CREATE,
        target_type="exercice",
        target_id=exercice.id,
        detail=libelle,
    )
    session.commit()
    session.refresh(exercice)
    return exercice


@router.post("/exercices/{exercice_id}/cloture", response_model=ClotureResult)
def cloturer_exercice(
    exercice_id: str,
    affectation: AffectationResultat,
    ctx: AccessContext = Depends(require_permission(Permission.EXERCISE_CLOSE)),
    session: Session = Depends(get_session),
):
    """Close a fiscal year: determine the result, carry balances forward, lock it.

    In one transaction: book the result-determination entry (class 6/7 → 120/129)
    in the closed year, open the next year (created if absent), post the report à
    nouveau in it — the balance-sheet accounts carried forward plus the chosen
    affectation of the result (report à nouveau 110/119 and/or reserves 106) —
    then mark the year clôturé. Both generated entries are validated on creation
    (official and immutable). Refused if a brouillon remains (validate or delete
    it first) or if the affectation does not equal the result.
    """
    aid = ctx.association_id
    exercice = owned_or_404(session, Exercice, exercice_id, aid, "Exercice introuvable")
    if exercice.statut == ExerciceStatut.CLOTURE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Exercice déjà clôturé."
        )

    draft = session.exec(
        select(Ecriture.id).where(
            Ecriture.association_id == aid,
            Ecriture.exercice_id == exercice_id,
            Ecriture.statut == EcritureStatut.BROUILLON,
        )
    ).first()
    if draft is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Validez ou supprimez les brouillons avant de clôturer l'exercice.",
        )

    soldes_gestion = _account_soldes(session, aid, exercice_id, list(CLASSES_GESTION))
    resultat = resultat_de_gestion(soldes_gestion)

    report_montant = affectation.report_a_nouveau.quantize(CENTS)
    reserves_montant = affectation.reserves.quantize(CENTS)
    if report_montant < ZERO or reserves_montant < ZERO:
        raise _bad_request("Les montants d'affectation ne peuvent pas être négatifs.")
    if report_montant + reserves_montant != abs(resultat):
        raise _bad_request(
            f"L'affectation ({report_montant + reserves_montant}) doit égaler "
            f"le résultat ({abs(resultat)})."
        )

    journal = session.exec(
        select(Journal).where(
            Journal.association_id == aid, Journal.code == _JOURNAL_CLOTURE
        )
    ).first()
    if journal is None:
        raise _bad_request("Référentiel comptable incomplet (journal OD absent).")
    c_excedent = _resolve_compte(session, aid, _COMPTE_EXCEDENT)
    c_deficit = _resolve_compte(session, aid, _COMPTE_DEFICIT)

    suivant = _resolve_next_exercice(session, aid, exercice)

    # Affect the result: excédent credits 110/106, déficit debits 119/106.
    affectation_lignes: list[tuple[str, Decimal, Decimal]] = []
    if resultat > ZERO:
        if report_montant > ZERO:
            report = _resolve_compte(session, aid, _REPORT_EXCEDENT)
            affectation_lignes.append((report.id, ZERO, report_montant))
        if reserves_montant > ZERO:
            reserves = _resolve_compte(session, aid, _RESERVES)
            affectation_lignes.append((reserves.id, ZERO, reserves_montant))
    elif resultat < ZERO:
        if report_montant > ZERO:
            report = _resolve_compte(session, aid, _REPORT_DEFICIT)
            affectation_lignes.append((report.id, report_montant, ZERO))
        if reserves_montant > ZERO:
            reserves = _resolve_compte(session, aid, _RESERVES)
            affectation_lignes.append((reserves.id, reserves_montant, ZERO))

    piece = next_numero_piece(session, aid)
    determination = build_ecriture_determination_resultat(
        association_id=aid,
        exercice_id=exercice.id,
        journal_id=journal.id,
        soldes_gestion=soldes_gestion,
        compte_excedent_id=c_excedent.id,
        compte_deficit_id=c_deficit.id,
        date_ecriture=exercice.date_fin,
        numero_piece=piece,
        created_by=ctx.user.id,
    )
    if determination is not None:
        _validate_now(determination, ctx.user.id)
        session.add(determination)
        piece += 1

    soldes_bilan = _account_soldes(session, aid, exercice_id, list(CLASSES_BILAN))
    report_entry = build_ecriture_report_a_nouveau(
        association_id=aid,
        exercice_id=suivant.id,
        journal_id=journal.id,
        soldes_bilan=soldes_bilan,
        affectation_lignes=affectation_lignes,
        date_ecriture=suivant.date_debut,
        numero_piece=piece,
        created_by=ctx.user.id,
    )
    if report_entry is not None:
        _validate_now(report_entry, ctx.user.id)
        session.add(report_entry)

    exercice.statut = ExerciceStatut.CLOTURE
    exercice.report_a_nouveau_genere = True
    session.add(exercice)
    record_audit(
        session,
        association_id=aid,
        actor_user_id=ctx.user.id,
        action=AuditAction.EXERCICE_CLOTURE,
        target_type="exercice",
        target_id=exercice.id,
        detail=(
            f"résultat={resultat} report={report_montant} réserves={reserves_montant}"
        ),
    )
    session.commit()
    session.refresh(exercice)
    session.refresh(suivant)

    return ClotureResult(
        resultat=resultat,
        report_a_nouveau=report_montant,
        reserves=reserves_montant,
        exercice_cloture=exercice,
        exercice_suivant=suivant,
    )
