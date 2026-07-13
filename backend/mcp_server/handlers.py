"""MCP tool handlers — thin adapters over the existing tenant-scoped services.

Every handler receives an already-authorized :class:`AccessContext` (the tool's
permission was checked by the dispatcher) and a live ``Session``. Reads reuse the
very same route/service functions the REST API exposes; assisted writes go
through the same entry builders — so there is one accounting truth, and entries
created via MCP are born *brouillon* like any other (never validated here).
"""

from datetime import date

from sqlmodel import Session, select

from auth_context import AccessContext
from exports.data.bilan import bilan_data
from exports.data.resultat import compte_resultat_data
from models import CategorieSaisie, SensCategorie
from routers.categories import list_categories
from routers.comptes.routes import balance_comptes, grand_livre, list_comptes
from routers.ecritures.routes import creer_saisie_simple, list_ecritures
from routers.ecritures.schemas import SaisieSimpleRequest
from routers.recus import list_dons
from routers.synthese.routes import get_synthese
from routers.synthese.service import default_range
from routers.tiers import CreateTiersRequest, creer_tiers
from routers.tresorerie.routes import list_tresorerie


class ToolError(Exception):
    """A user-facing tool failure (bad argument, unknown reference)."""


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise ToolError(f"Date invalide : {value!r} (attendu AAAA-MM-JJ).") from exc


def _resolve_categorie(
    session: Session, association_id: str, sens: SensCategorie, ref: str
) -> CategorieSaisie:
    """Resolve a category by id or exact libellé (case-insensitive), for ``sens``.

    Restricting to the operation's sens is what keeps a recette from being booked
    under a dépense category. An ambiguous or unknown reference raises with the
    available options so the assistant can correct itself.
    """
    ref = (ref or "").strip()
    candidates = session.exec(
        select(CategorieSaisie).where(
            CategorieSaisie.association_id == association_id,
            CategorieSaisie.sens == sens,
            CategorieSaisie.is_active.is_(True),
        )
    ).all()
    for cat in candidates:
        if cat.id == ref:
            return cat
    matches = [c for c in candidates if c.libelle.strip().lower() == ref.lower()]
    if len(matches) == 1:
        return matches[0]
    available = ", ".join(sorted(c.libelle for c in candidates)) or "(aucune)"
    if not matches:
        raise ToolError(
            f"Catégorie {ref!r} introuvable pour ce type. Catégories : {available}."
        )
    raise ToolError(f"Catégorie {ref!r} ambiguë. Précisez l'identifiant.")


# --- Read tools ----------------------------------------------------------


def h_get_synthese(ctx: AccessContext, session: Session, args: dict):
    return get_synthese(
        date_from=_parse_date(args.get("date_from")),
        date_to=_parse_date(args.get("date_to")),
        ctx=ctx,
        session=session,
    )


def h_list_ecritures(ctx: AccessContext, session: Session, args: dict):
    return list_ecritures(
        date_from=_parse_date(args.get("date_from")),
        date_to=_parse_date(args.get("date_to")),
        q=(args.get("q") or None),
        limit=int(args.get("limit", 50)),
        ctx=ctx,
        session=session,
    )


def h_balance_comptes(ctx: AccessContext, session: Session, args: dict):
    return balance_comptes(
        exercice_id=args.get("exercice_id"), ctx=ctx, session=session
    )


def h_grand_livre(ctx: AccessContext, session: Session, args: dict):
    compte_id = (args.get("compte_id") or "").strip()
    if not compte_id:
        raise ToolError("compte_id est requis.")
    return grand_livre(
        compte_id=compte_id,
        exercice_id=args.get("exercice_id"),
        ctx=ctx,
        session=session,
    )


def h_compte_resultat(ctx: AccessContext, session: Session, args: dict):
    default_from, default_to = default_range(session, ctx.association_id)
    date_from = _parse_date(args.get("date_from")) or default_from
    date_to = _parse_date(args.get("date_to")) or default_to
    return compte_resultat_data(session, ctx.association_id, date_from, date_to)


def h_bilan(ctx: AccessContext, session: Session, args: dict):
    _, default_to = default_range(session, ctx.association_id)
    date_to = _parse_date(args.get("date_to")) or default_to
    return bilan_data(session, ctx.association_id, date_to)


def h_list_comptes(ctx: AccessContext, session: Session, args: dict):
    return list_comptes(ctx=ctx, session=session)


def h_list_comptes_tresorerie(ctx: AccessContext, session: Session, args: dict):
    return list_tresorerie(ctx=ctx, session=session)


def h_list_categories(ctx: AccessContext, session: Session, args: dict):
    return list_categories(ctx=ctx, session=session)


def h_list_dons(ctx: AccessContext, session: Session, args: dict):
    return list_dons(
        annee=args.get("annee"),
        only_unreceipted=bool(args.get("only_unreceipted", False)),
        ctx=ctx,
        session=session,
    )


# --- Assisted-write tools (always create a brouillon) --------------------


def _saisir(ctx: AccessContext, session: Session, args: dict, sens: SensCategorie):
    montant = args.get("montant")
    if montant is None:
        raise ToolError("montant est requis.")
    categorie = _resolve_categorie(
        session, ctx.association_id, sens, args.get("categorie", "")
    )
    compte_ref = (args.get("compte_tresorerie") or "").strip()
    if not compte_ref:
        raise ToolError("compte_tresorerie est requis.")
    comptes = list_tresorerie(ctx=ctx, session=session)
    compte = next(
        (
            c
            for c in comptes
            if c.id == compte_ref or c.libelle.strip().lower() == compte_ref.lower()
        ),
        None,
    )
    if compte is None:
        options = ", ".join(sorted(c.libelle for c in comptes)) or "(aucun)"
        raise ToolError(
            f"Compte de trésorerie {compte_ref!r} introuvable. Comptes : {options}."
        )

    body = SaisieSimpleRequest(
        categorie_id=categorie.id,
        compte_tresorerie_id=compte.id,
        montant=montant,
        date=_parse_date(args.get("date")) or date.today(),
        libelle=(args.get("libelle") or None),
    )
    # Reuses the REST creation path exactly: born brouillon, audited, balanced.
    ecriture = creer_saisie_simple(body=body, ctx=ctx, session=session)
    return {
        "status": "brouillon_cree",
        "message": "Écriture créée en brouillon, à valider dans l'application.",
        "ecriture_id": ecriture.id,
        "numero_piece": ecriture.numero_piece,
        "date": ecriture.date,
        "libelle": ecriture.libelle,
        "montant": montant,
        "categorie": categorie.libelle,
        "compte_tresorerie": compte.libelle,
        "statut": ecriture.statut,
    }


def h_saisir_recette(ctx: AccessContext, session: Session, args: dict):
    return _saisir(ctx, session, args, SensCategorie.RECETTE)


def h_saisir_depense(ctx: AccessContext, session: Session, args: dict):
    return _saisir(ctx, session, args, SensCategorie.DEPENSE)


def h_creer_tiers(ctx: AccessContext, session: Session, args: dict):
    nom = (args.get("nom") or "").strip()
    if not nom:
        raise ToolError("nom est requis.")
    type_raw = (args.get("type") or "fournisseur").strip()
    from models import TypeTiers

    try:
        type_tiers = TypeTiers(type_raw)
    except ValueError as exc:
        allowed = ", ".join(t.value for t in TypeTiers)
        raise ToolError(f"type invalide. Valeurs : {allowed}.") from exc
    body = CreateTiersRequest(nom=nom, type=type_tiers)
    tiers = creer_tiers(body=body, ctx=ctx, session=session)
    return {
        "status": "cree",
        "tiers_id": tiers.id,
        "nom": tiers.nom,
        "type": tiers.type,
    }
