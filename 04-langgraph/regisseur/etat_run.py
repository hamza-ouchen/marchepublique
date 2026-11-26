# ═══════════════════════════════════════════════════════════════════
# SOU9NA — RÉGISSEUR · état d'un run (LangGraph StateGraph)
# L'état circule de nœud en nœud ; chaque nœud renvoie une mise à jour
# partielle. Les listes et le rapport sont **fusionnés** (reducers) —
# jamais écrasés d'un nœud à l'autre.
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import operator
from typing import Annotated
from typing import TypedDict


class EtatRun(TypedDict, total=False):
    run_id: str                       # ex. "run-2026-11-17-cron-ab12cd"
    mode: str                         # cron | manuel | backfill
    date: str                         # "2026-11-17"
    company_id: str                   # entreprise cible (enveloppe cahier §5.1)
    request_id: str                   # corrélateur de bout en bout
    collecte: str                     # auto | full | incremental | none
    demo: bool                        # True = agents simulés (rapports de test)
    message: str                      # entrée libre (chat) — facultatif en pipeline
    etapes: Annotated[list[str], operator.add]   # journal ordonné, fusionné
    rapport: Annotated[dict, operator.or_]     # métriques cumulées, fusionné
    erreurs: Annotated[list[str], operator.add]  # une erreur = étapes sautées
    gates: Annotated[list[str], operator.add]    # trace des 3 portes
    intention: str                    # opportunités | digest | sante | profil | hors_perimetre
    rejete: bool                      # True = rejet par une porte (terminus rejet_gate)
    statut: str                       # en_cours | echec | cloture | rejete


def nouvel_etat(mode: str, date: str, demo: bool, run_id: str,
                company_id: str = "", request_id: str = "",
                collecte: str = "") -> EtatRun:
    return {
        "run_id": run_id,
        "mode": mode,
        "date": date,
        "company_id": company_id,
        "request_id": request_id,
        "collecte": collecte,
        "demo": demo,
        "etapes": [],
        "rapport": {},
        "erreurs": [],
        "gates": [],
        "intention": "ambigu",
        "rejete": False,
        "statut": "en_cours",
    }
