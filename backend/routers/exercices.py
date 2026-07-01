"""Fiscal-year (exercice) lifecycle: listing, creation and closing.

Any active member may list the association's fiscal years (they are building
blocks of forms and reports). Opening a new year and closing one are structural
accounting acts, gated by :data:`Permission.EXERCISE_CLOSE`. Closing generates
the result-determination and report-à-nouveau entries and locks the year; it
lives in ``cloture.py`` and is exposed here.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlmodel import Session, desc, select

from accounting_engine import (
    CENTS,
    ZERO,
    build_ecriture_determination_resultat,
    build_ecriture_report_a_nouveau,
    find_exercice_covering,
    next_numero_piece,
    resultat_de_gestion,
    validated_only,
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
    Compte,
    Ecriture,
    EcritureStatut,
    Exercice,
    ExerciceCreate,
    ExerciceRead,
    ExerciceStatut,
    Journal,
    LigneEcriture,
)

router = APIRouter(prefix="/api/asso/{association_id}", tags=["exercices"])

_JOURNAL_CLOTURE = "OD"  # opérations diverses
# Result accounts: excédent (120) / déficit (129) and their affectation targets.
_COMPTE_EXCEDENT = "120"
_COMPTE_DEFICIT = "129"
_REPORT_EXCEDENT = "110"  # report à nouveau créditeur
_REPORT_DEFICIT = "119"  # report à nouveau débiteur
_RESERVES = "106"


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _account_soldes(
    session: Session, association_id: str, exercice_id: str, classes: list[int]
) -> list[tuple[str, Decimal]]:
    """Per-account solde (Σdébit − Σcrédit) within an exercice, validated only."""
    debit = func.coalesce(func.sum(LigneEcriture.debit), 0)
    credit = func.coalesce(func.sum(LigneEcriture.credit), 0)
    rows = session.exec(
        select(Compte.id, Compte.numero, debit, credit)
        .select_from(LigneEcriture)
        .join(Ecriture, Ecriture.id == LigneEcriture.ecriture_id)
        .join(Compte, Compte.id == LigneEcriture.compte_id)
        .where(
            Ecriture.association_id == association_id,
            Compte.association_id == association_id,
            Ecriture.exercice_id == exercice_id,
            Compte.classe.in_(classes),
            validated_only(),
        )
        .group_by(Compte.id, Compte.numero)
    ).all()
    result: list[tuple[str, Decimal]] = []
    for compte_id, numero, d, c in rows:
        # The result account (12) is not a carried-forward balance: it is
        # affected explicitly, so keep it out of the report à nouveau.
        if numero.startswith("12"):
            continue
        solde = (Decimal(str(d)) - Decimal(str(c))).quantize(CENTS)
        if solde != ZERO:
            result.append((compte_id, solde))
    return result


def _resolve_compte(session: Session, association_id: str, numero: str) -> Compte:
    compte = session.exec(
        select(Compte).where(
            Compte.association_id == association_id, Compte.numero == numero
        )
    ).first()
    if compte is None:
        raise _bad_request(f"Référentiel comptable incomplet (compte {numero} absent).")
    return compte


def _next_period(prev: Exercice) -> tuple[date, date, str]:
    """Default period for the year following ``prev``: the day after it ends,
    spanning one year (same anniversary), with a civil or straddling label."""
    debut = prev.date_fin + timedelta(days=1)
    try:
        fin = debut.replace(year=debut.year + 1) - timedelta(days=1)
    except ValueError:  # 29 Feb -> the next year has no 29 Feb
        fin = date(debut.year + 1, 3, 1) - timedelta(days=1)
    libelle = str(debut.year) if debut.year == fin.year else f"{debut.year}-{fin.year}"
    return debut, fin, libelle


def _resolve_next_exercice(
    session: Session, association_id: str, prev: Exercice
) -> Exercice:
    """The fiscal year following ``prev``: an existing one, else created."""
    next_debut = prev.date_fin + timedelta(days=1)
    suivant = find_exercice_covering(session, association_id, next_debut)
    if suivant is not None:
        if suivant.statut == ExerciceStatut.CLOTURE:
            raise _bad_request("L'exercice suivant est déjà clôturé.")
        return suivant

    debut, fin, libelle = _next_period(prev)
    overlap = session.exec(
        select(Exercice.id).where(
            Exercice.association_id == association_id,
            Exercice.date_debut <= fin,
            Exercice.date_fin >= debut,
        )
    ).first()
    if overlap is not None:
        raise _bad_request(
            "Impossible de créer l'exercice suivant (chevauchement) — "
            "créez-le manuellement."
        )
    suivant = Exercice(
        association_id=association_id,
        libelle=libelle,
        date_debut=debut,
        date_fin=fin,
    )
    session.add(suivant)
    session.flush()  # need its id for the report à nouveau entry
    return suivant


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

    soldes_gestion = _account_soldes(session, aid, exercice_id, [6, 7])
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

    soldes_bilan = _account_soldes(session, aid, exercice_id, [1, 2, 3, 4, 5])
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


def _validate_now(ecriture: Ecriture, user_id: str) -> None:
    """Stamp a generated closing entry as validated (official, immutable)."""
    ecriture.statut = EcritureStatut.VALIDEE
    ecriture.validated_by = user_id
    ecriture.validated_at = datetime.now(UTC)
