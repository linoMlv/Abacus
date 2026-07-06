"""The MCP tool catalog: one declarative spec per tool.

Each tool names the fine-grained :class:`~authz.Permission` it requires. The
server advertises only the tools a key's *effective* permissions allow, and the
dispatcher re-checks the permission before running (the advertised list is a
convenience, never the authorization). Only read and assisted-write tools exist
— there is deliberately no tool to validate, delete or close (plan §7 guardrail).
"""

from collections.abc import Callable
from dataclasses import dataclass

from authz import Permission

from . import handlers

# A short ISO-date argument reused by several tools.
_DATE = {"type": "string", "description": "Date AAAA-MM-JJ (optionnel)."}


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict
    permission: Permission
    handler: Callable
    writes: bool = False


TOOL_SPECS: tuple[ToolSpec, ...] = (
    # --- Consultation ---
    ToolSpec(
        name="get_synthese",
        description=(
            "Synthèse de l'association sur une période (résultat, répartitions, "
            "courbe de trésorerie, alertes). Sans dates : l'exercice ouvert."
        ),
        input_schema={
            "type": "object",
            "properties": {"date_from": _DATE, "date_to": _DATE},
        },
        permission=Permission.DASHBOARD_VIEW,
        handler=handlers.h_get_synthese,
    ),
    ToolSpec(
        name="list_ecritures",
        description=(
            "Journal : écritures de l'association (plus récentes d'abord), avec "
            "filtres période, recherche texte et limite."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "date_from": _DATE,
                "date_to": _DATE,
                "q": {"type": "string", "description": "Recherche libellé."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
        },
        permission=Permission.REPORT_VIEW,
        handler=handlers.h_list_ecritures,
    ),
    ToolSpec(
        name="balance_comptes",
        description="Balance des comptes (débit/crédit/solde par compte mouvementé).",
        input_schema={
            "type": "object",
            "properties": {
                "exercice_id": {
                    "type": "string",
                    "description": "Exercice (optionnel).",
                }
            },
        },
        permission=Permission.REPORT_VIEW,
        handler=handlers.h_balance_comptes,
    ),
    ToolSpec(
        name="grand_livre",
        description="Grand livre d'un compte : mouvements datés + solde cumulé.",
        input_schema={
            "type": "object",
            "properties": {
                "compte_id": {
                    "type": "string",
                    "description": "Identifiant du compte.",
                },
                "exercice_id": {"type": "string"},
            },
            "required": ["compte_id"],
        },
        permission=Permission.REPORT_VIEW,
        handler=handlers.h_grand_livre,
    ),
    ToolSpec(
        name="compte_resultat",
        description="Compte de résultat (produits cl.7 − charges cl.6) sur la période.",
        input_schema={
            "type": "object",
            "properties": {"date_from": _DATE, "date_to": _DATE},
        },
        permission=Permission.REPORT_VIEW,
        handler=handlers.h_compte_resultat,
    ),
    ToolSpec(
        name="bilan",
        description="Bilan (soldes des classes 1 à 5) à une date de clôture.",
        input_schema={"type": "object", "properties": {"date_to": _DATE}},
        permission=Permission.REPORT_VIEW,
        handler=handlers.h_bilan,
    ),
    ToolSpec(
        name="list_comptes",
        description="Plan comptable de l'association (numéro, libellé, classe).",
        input_schema={"type": "object", "properties": {}},
        permission=Permission.REPORT_VIEW,
        handler=handlers.h_list_comptes,
    ),
    ToolSpec(
        name="list_comptes_tresorerie",
        description=(
            "Comptes de trésorerie nommés (banque/caisse…) avec leur solde — "
            "utile pour référencer un compte lors d'une saisie."
        ),
        input_schema={"type": "object", "properties": {}},
        permission=Permission.DASHBOARD_VIEW,
        handler=handlers.h_list_comptes_tresorerie,
    ),
    ToolSpec(
        name="list_categories",
        description=(
            "Catégories de saisie (libellé, sens recette/dépense) — utile pour "
            "référencer une catégorie lors d'une saisie."
        ),
        input_schema={"type": "object", "properties": {}},
        permission=Permission.DASHBOARD_VIEW,
        handler=handlers.h_list_categories,
    ),
    ToolSpec(
        name="list_dons",
        description="Dons (recettes rattachées à un donateur) et statut de reçu.",
        input_schema={
            "type": "object",
            "properties": {
                "annee": {"type": "integer", "description": "Année civile."},
                "only_unreceipted": {"type": "boolean"},
            },
        },
        permission=Permission.DONATION_MANAGE,
        handler=handlers.h_list_dons,
    ),
    # --- Assisted write (brouillon only) ---
    ToolSpec(
        name="saisir_recette",
        description=(
            "Enregistre une RECETTE en brouillon (à valider ensuite dans l'appli). "
            "La catégorie et le compte se donnent par nom ou identifiant."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "montant": {"type": "number", "description": "Montant en euros."},
                "categorie": {"type": "string", "description": "Catégorie recette."},
                "compte_tresorerie": {
                    "type": "string",
                    "description": "Compte crédité.",
                },
                "date": _DATE,
                "libelle": {"type": "string"},
            },
            "required": ["montant", "categorie", "compte_tresorerie"],
        },
        permission=Permission.ENTRY_CREATE_SIMPLE,
        handler=handlers.h_saisir_recette,
        writes=True,
    ),
    ToolSpec(
        name="saisir_depense",
        description=(
            "Enregistre une DÉPENSE en brouillon (à valider ensuite dans l'appli). "
            "La catégorie et le compte se donnent par nom ou identifiant."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "montant": {"type": "number", "description": "Montant en euros."},
                "categorie": {"type": "string", "description": "Catégorie dépense."},
                "compte_tresorerie": {
                    "type": "string",
                    "description": "Compte débité.",
                },
                "date": _DATE,
                "libelle": {"type": "string"},
            },
            "required": ["montant", "categorie", "compte_tresorerie"],
        },
        permission=Permission.ENTRY_CREATE_SIMPLE,
        handler=handlers.h_saisir_depense,
        writes=True,
    ),
    ToolSpec(
        name="creer_tiers",
        description="Crée un tiers (fournisseur/client/donateur/financeur).",
        input_schema={
            "type": "object",
            "properties": {
                "nom": {"type": "string"},
                "type": {
                    "type": "string",
                    "enum": [
                        "fournisseur",
                        "client",
                        "donateur",
                        "financeur",
                        "autre",
                    ],
                },
            },
            "required": ["nom"],
        },
        permission=Permission.TIERS_MANAGE,
        handler=handlers.h_creer_tiers,
        writes=True,
    ),
)

TOOLS_BY_NAME: dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}
